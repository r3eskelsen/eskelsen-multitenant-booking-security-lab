import os
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

tenants = [
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
]
backend_ids = set()

with ConnectionPool(
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
    max_size=1,
    timeout=10,
) as pool:
    pool.wait()
    with pool.connection() as connection:
        role = connection.execute(
            "SELECT current_user AS name, rolsuper, rolbypassrls "
            "FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        assert role["name"] == "lab03_app"
        assert not role["rolsuper"] and not role["rolbypassrls"]
    print("PASS POOL01: authenticated connection uses limited application role")

    for index in range(40):
        tenant = tenants[index % 2]
        with pool.connection() as connection:
            with connection.transaction():
                backend_ids.add(connection.execute(
                    "SELECT pg_backend_pid() AS pid"
                ).fetchone()["pid"])
                connection.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (tenant,),
                )
                rows = connection.execute(
                    "SELECT id FROM booking.tenants"
                ).fetchall()
                assert [str(row["id"]) for row in rows] == [tenant]

        with pool.connection() as connection:
            with connection.transaction():
                value = connection.execute(
                    "SELECT current_setting('app.tenant_id', true) AS tenant"
                ).fetchone()["tenant"]
                assert value in (None, "")
                assert connection.execute(
                    "SELECT count(*) AS n FROM booking.tenants"
                ).fetchone()["n"] == 0

    assert len(backend_ids) == 1
    print("PASS POOL02: 40 alternating tenant transactions on one backend")
    print("PASS POOL03: committed transactions leave no tenant context")

    try:
        with pool.connection() as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (tenants[0],),
                )
                raise ValueError("Synthetic rollback trigger")
    except ValueError:
        pass

    with pool.connection() as connection:
        with connection.transaction():
            assert connection.execute(
                "SELECT current_setting('app.tenant_id', true) AS tenant"
            ).fetchone()["tenant"] in (None, "")
            assert connection.execute(
                "SELECT count(*) AS n FROM booking.tenants"
            ).fetchone()["n"] == 0

    print("PASS POOL04: rollback leaves no tenant context")

print("APPLICATION ROLE AND POOL ISOLATION PASS")