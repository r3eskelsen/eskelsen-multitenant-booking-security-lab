import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt

BASE = "http://127.0.0.1:8000"
SECRET = os.environ["LAB03_JWT_SECRET"]
PRO_A = "11111111-1111-4111-8111-111111111111"
PRO_B = "22222222-2222-4222-8222-222222222222"
TENANT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
RUN = uuid4().hex
created = set()
results = []


def token(subject, expired=False, extra=None):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=-1 if expired else 20),
        "iss": "esk-lab03",
        "aud": "esk-lab03-api",
    }
    claims.update(extra or {})
    return jwt.encode(claims, SECRET, algorithm="HS256")


A = token("synthetic-user-a")
B = token("synthetic-user-b")


def request(method, path, credential=None, body=None, key=None):
    headers = {}
    if credential:
        headers["Authorization"] = "Bearer " + credential
    if key:
        headers["Idempotency-Key"] = key
    with httpx.Client(base_url=BASE, timeout=30, trust_env=False) as client:
        return client.request(method, path, headers=headers, json=body)


def check(name, condition):
    results.append({"case": name, "status": "PASS" if condition else "FAIL"})
    print(("PASS " if condition else "FAIL ") + name, flush=True)
    if not condition:
        raise AssertionError(name)


def remember(response):
    if response.status_code == 201:
        created.add(response.json()["booking"]["id"])


# Use a run-specific future interval without real personal data.
start = datetime(2090, 1, 1, tzinfo=timezone.utc) + timedelta(
    seconds=int(RUN[:10], 16) % (5 * 365 * 86400)
)


def payload(offset=0):
    value = start + timedelta(hours=offset)
    return {
        "professional_id": PRO_A,
        "starts_at": value.isoformat(),
        "ends_at": (value + timedelta(hours=1)).isoformat(),
    }


failure = False
cleanup_failed = False

try:
    check("HTTP01 missing authentication",
          request("GET", "/bookings").status_code == 401)
    check("HTTP02 invalid token",
          request("GET", "/bookings", "invalid").status_code == 401)
    check("HTTP03 expired token",
          request("GET", "/bookings",
                  token("synthetic-user-a", expired=True)).status_code == 401)

    response = request("GET", "/professionals", A)
    check("HTTP04 tenant A professionals",
          response.status_code == 200
          and [row["id"] for row in response.json()] == [PRO_A])

    response = request("GET", "/professionals", B)
    check("HTTP05 tenant B professionals",
          response.status_code == 200
          and [row["id"] for row in response.json()] == [PRO_B])

    spoofed_claim = token(
        "synthetic-user-a", extra={"tenant_id": TENANT_B}
    )
    response = request("GET", "/professionals", spoofed_claim)
    check("HTTP06 tenant claim cannot override server identity",
          response.status_code == 200
          and [row["id"] for row in response.json()] == [PRO_A])

    forged = dict(payload(), tenant_id=TENANT_B)
    response = request("POST", "/bookings", A, forged, RUN + "-forged")
    remember(response)
    check("HTTP07 client tenant field rejected", response.status_code == 422)

    foreign = dict(payload(), professional_id=PRO_B)
    response = request("POST", "/bookings", A, foreign, RUN + "-foreign")
    remember(response)
    check("HTTP08 foreign professional hidden", response.status_code == 404)

    response = request("POST", "/bookings", A, payload(), RUN + "-initial")
    remember(response)
    check("HTTP09 own booking created", response.status_code == 201)
    booking_id = response.json()["booking"]["id"]
    check("HTTP10 created booking belongs to tenant A",
          response.json()["booking"]["tenant_id"] == TENANT_A)

    check("HTTP11 cross-tenant read hidden",
          request("GET", "/bookings/" + booking_id, B).status_code == 404)
    check("HTTP12 cross-tenant update denied",
          request("PATCH", "/bookings/" + booking_id, B,
                  {"status": "cancelled"}).status_code == 404)
    check("HTTP13 cross-tenant delete denied",
          request("DELETE", "/bookings/" + booking_id, B).status_code == 404)

    response = request("GET", "/bookings/" + booking_id, A)
    check("HTTP14 original remains confirmed",
          response.status_code == 200
          and response.json()["status"] == "confirmed")

    response = request("POST", "/bookings", A, payload(), RUN + "-initial")
    remember(response)
    check("HTTP15 identical replay",
          response.status_code == 201
          and response.json()["replayed"] is True
          and response.json()["booking"]["id"] == booking_id)

    response = request("POST", "/bookings", A, payload(3), RUN + "-initial")
    remember(response)
    check("HTTP16 changed payload conflicts", response.status_code == 409)

    response = request("POST", "/bookings", A, payload(1), RUN + "-adjacent")
    remember(response)
    check("HTTP17 adjacent interval accepted", response.status_code == 201)

    invalid = payload(5)
    invalid["ends_at"] = invalid["starts_at"]
    response = request("POST", "/bookings", A, invalid, RUN + "-invalid")
    remember(response)
    check("HTTP18 empty interval rejected", response.status_code == 422)

    def competing(index):
        return request(
            "POST", "/bookings", A, payload(24),
            RUN + "-competition-" + str(index),
        )

    with ThreadPoolExecutor(max_workers=12) as executor:
        responses = list(executor.map(competing, range(12)))
    for response in responses:
        remember(response)
    statuses = [response.status_code for response in responses]
    print("CONCURRENCY distinct keys: " + json.dumps(statuses), flush=True)
    check("HTTP19 competing bookings: one success and eleven conflicts",
          statuses.count(201) == 1 and statuses.count(409) == 11)

    def same_key(index):
        return request(
            "POST", "/bookings", A, payload(48), RUN + "-same-key"
        )

    with ThreadPoolExecutor(max_workers=12) as executor:
        responses = list(executor.map(same_key, range(12)))
    for response in responses:
        remember(response)
    statuses = [response.status_code for response in responses]
    print("CONCURRENCY same key: " + json.dumps(statuses), flush=True)
    check("HTTP20 concurrent identical requests all succeed",
          all(status == 201 for status in statuses))
    check("HTTP21 concurrent identical requests return one booking",
          len({response.json()["booking"]["id"]
               for response in responses}) == 1)
    check("HTTP22 exactly one original and eleven replays",
          sum(response.json()["replayed"] is False
              for response in responses) == 1)

    response = request("GET", "/bookings", A)
    check("HTTP23 list contains each test booking once",
          response.status_code == 200
          and all(
              sum(row["id"] == identifier for row in response.json()) == 1
              for identifier in created
          ))

except Exception as exc:
    failure = True
    # Avoid dumping requests, headers or tokens on failure.
    print("TEST RUN FAILED: " + type(exc).__name__, flush=True)

finally:
    for identifier in sorted(created):
        try:
            response = request("DELETE", "/bookings/" + identifier, A)
            if response.status_code != 200:
                cleanup_failed = True
        except Exception:
            cleanup_failed = True

    print("SUMMARY " + json.dumps({
        "run_id": RUN,
        "results": results,
        "synthetic_bookings_created": len(created),
        "cleanup": "FAIL" if cleanup_failed else "PASS",
        "cleanup_action": "cancel tracked synthetic bookings; preserve history",
    }), flush=True)

if failure or cleanup_failed:
    raise SystemExit(1)

print("HTTP AND CONCURRENCY CHECKS PASS", flush=True)