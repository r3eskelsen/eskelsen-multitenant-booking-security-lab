"""Independent synthetic booking laboratory."""
import hashlib
import json
import os
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

import jwt
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, model_validator

TENANT_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

# Server-owned synthetic identity registry. Never supplied by request body.
IDENTITIES = {
    "synthetic-user-a": (
        TENANT_A, UUID("aaaaaaaa-0000-4000-8000-000000000001")
    ),
    "synthetic-user-b": (
        TENANT_B, UUID("bbbbbbbb-0000-4000-8000-000000000001")
    ),
}

secret = os.environ["LAB03_JWT_SECRET"]
if len(secret) < 32:
    raise RuntimeError("JWT secret must contain at least 32 characters")

pool = ConnectionPool(
    conninfo="",
    kwargs={
        "host": "db",
        "dbname": "booking_lab",
        "user": "lab03_app",
        "password": os.environ["LAB03_APP_PASSWORD"],
        "row_factory": dict_row,
        "connect_timeout": 5,
    },
    min_size=1,
    max_size=4,
    timeout=10,
    open=False,
)


@asynccontextmanager
async def lifespan(app):
    pool.open(wait=True)
    try:
        yield
    finally:
        pool.close()


app = FastAPI(
    title="Eskelsen Booking & Security Lab",
    version="0.1.0",
    lifespan=lifespan,
)
bearer = HTTPBearer(auto_error=False)


def identity(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer)
    ],
):
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    try:
        claims = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            issuer="esk-lab03",
            audience="esk-lab03-api",
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
        return IDENTITIES[claims["sub"]]
    except (jwt.InvalidTokenError, KeyError, TypeError):
        raise HTTPException(401, "Invalid authentication") from None


@contextmanager
def transaction(principal):
    tenant, user = principal
    with pool.connection() as connection:
        with connection.transaction():
            connection.execute(
                "SELECT set_config('app.tenant_id', %s, true), "
                "set_config('app.user_id', %s, true)",
                (str(tenant), str(user)),
            )
            yield connection


class BookingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    professional_id: UUID
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def validate_interval(self):
        for value in (self.starts_at, self.ends_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timezone-aware timestamps required")
        self.starts_at = self.starts_at.astimezone(timezone.utc)
        self.ends_at = self.ends_at.astimezone(timezone.utc)
        if self.starts_at >= self.ends_at:
            raise ValueError("End must follow start")
        return self


class StatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str

    @model_validator(mode="after")
    def validate_status(self):
        if self.status != "cancelled":
            raise ValueError("Only cancellation is supported")
        return self


def find_booking(connection, booking_id):
    row = connection.execute(
        "SELECT * FROM booking.bookings WHERE id = %s",
        (booking_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Booking not found")
    return row


@app.get("/health")
def health():
    with pool.connection() as connection:
        connection.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/professionals")
def professionals(principal=Depends(identity)):
    with transaction(principal) as connection:
        return connection.execute(
            "SELECT id, name FROM booking.professionals ORDER BY id"
        ).fetchall()


@app.get("/bookings")
def bookings(principal=Depends(identity)):
    with transaction(principal) as connection:
        return connection.execute(
            "SELECT * FROM booking.bookings ORDER BY starts_at, id"
        ).fetchall()


@app.get("/bookings/{booking_id}")
def booking(booking_id: UUID, principal=Depends(identity)):
    with transaction(principal) as connection:
        return find_booking(connection, booking_id)


@app.post("/bookings", status_code=201)
def create_booking(
    body: BookingInput,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128)
    ],
    principal=Depends(identity),
):
    tenant, user = principal
    payload = json.dumps(
        body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    lock_material = json.dumps([str(tenant), str(user), idempotency_key])
    lock_id = int.from_bytes(
        hashlib.sha256(lock_material.encode()).digest()[:8],
        byteorder="big",
        signed=True,
    )
    try:
        with transaction(principal) as connection:
            # Serialize identical tenant/user/key requests until commit.
            connection.execute(
                "SELECT pg_advisory_xact_lock(%s)", (lock_id,)
            )
            prior = connection.execute(
                "SELECT request_hash, booking_id FROM booking.idempotency "
                "WHERE tenant_id = %s AND user_id = %s AND key = %s",
                (tenant, user, idempotency_key),
            ).fetchone()
            if prior:
                if prior["request_hash"] != fingerprint:
                    raise HTTPException(409, "Idempotency key conflict")
                return {
                    "booking": find_booking(connection, prior["booking_id"]),
                    "replayed": True,
                }

            professional = connection.execute(
                "SELECT id FROM booking.professionals WHERE id = %s",
                (body.professional_id,),
            ).fetchone()
            if professional is None:
                raise HTTPException(404, "Professional not found")

            booking_id = uuid4()
            row = connection.execute(
                "INSERT INTO booking.bookings "
                "(tenant_id,id,professional_id,starts_at,ends_at) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING *",
                (tenant, booking_id, body.professional_id,
                 body.starts_at, body.ends_at),
            ).fetchone()
            connection.execute(
                "INSERT INTO booking.idempotency "
                "(tenant_id,user_id,key,request_hash,booking_id) "
                "VALUES (%s,%s,%s,%s,%s)",
                (tenant, user, idempotency_key, fingerprint, booking_id),
            )
            return {"booking": row, "replayed": False}
    except psycopg.errors.ExclusionViolation:
        raise HTTPException(409, "Booking interval unavailable") from None
    except psycopg.errors.CheckViolation:
        raise HTTPException(422, "Invalid booking interval") from None


@app.patch("/bookings/{booking_id}")
def cancel_booking(
    booking_id: UUID,
    body: StatusInput,
    principal=Depends(identity),
):
    with transaction(principal) as connection:
        row = connection.execute(
            "UPDATE booking.bookings SET status = %s "
            "WHERE id = %s RETURNING *",
            (body.status, booking_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Booking not found")
        return row


@app.delete("/bookings/{booking_id}")
def delete_booking(booking_id: UUID, principal=Depends(identity)):
    # Preserve booking history and idempotency references.
    with transaction(principal) as connection:
        row = connection.execute(
            "UPDATE booking.bookings SET status = 'cancelled' "
            "WHERE id = %s RETURNING *",
            (booking_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Booking not found")
        return {"id": row["id"], "status": row["status"]}