\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE lab03_app;

DO $test$
BEGIN
    IF current_user <> 'lab03_app' THEN
        RAISE EXCEPTION 'FAIL: unexpected role';
    END IF;

    PERFORM set_config('app.tenant_id', '', true);
    PERFORM set_config('app.user_id', '', true);

    IF EXISTS (SELECT 1 FROM booking.tenants)
       OR EXISTS (SELECT 1 FROM booking.professionals)
       OR EXISTS (SELECT 1 FROM booking.bookings)
       OR EXISTS (SELECT 1 FROM booking.idempotency) THEN
        RAISE EXCEPTION 'FAIL: missing tenant context exposes rows';
    END IF;
    RAISE NOTICE 'PASS DB01: missing context exposes no rows';

    PERFORM set_config(
        'app.tenant_id', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true
    );

    IF (SELECT count(*) FROM booking.tenants) <> 1
       OR NOT EXISTS (
           SELECT 1 FROM booking.tenants
           WHERE id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
       )
       OR (SELECT count(*) FROM booking.professionals) <> 1 THEN
        RAISE EXCEPTION 'FAIL: tenant A visibility';
    END IF;
    RAISE NOTICE 'PASS DB02: tenant A sees its own fixtures only';

    BEGIN
        INSERT INTO booking.bookings VALUES (
            'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
            '90000000-0000-4000-8000-000000000001',
            '22222222-2222-4222-8222-222222222222',
            '2099-01-01 10:00:00+00',
            '2099-01-01 11:00:00+00',
            'confirmed'
        );
        RAISE EXCEPTION 'FAIL: cross-tenant insert accepted';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS DB03: forged tenant insert rejected';
    END;

    INSERT INTO booking.bookings VALUES (
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        '90000000-0000-4000-8000-000000000002',
        '11111111-1111-4111-8111-111111111111',
        '2099-01-01 10:00:00+00',
        '2099-01-01 11:00:00+00',
        'confirmed'
    );

    BEGIN
        INSERT INTO booking.bookings VALUES (
            'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
            '90000000-0000-4000-8000-000000000003',
            '11111111-1111-4111-8111-111111111111',
            '2099-01-01 10:30:00+00',
            '2099-01-01 11:30:00+00',
            'confirmed'
        );
        RAISE EXCEPTION 'FAIL: overlapping booking accepted';
    EXCEPTION WHEN exclusion_violation THEN
        RAISE NOTICE 'PASS DB04: overlapping booking rejected';
    END;

    INSERT INTO booking.bookings VALUES (
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        '90000000-0000-4000-8000-000000000004',
        '11111111-1111-4111-8111-111111111111',
        '2099-01-01 11:00:00+00',
        '2099-01-01 12:00:00+00',
        'confirmed'
    );
    RAISE NOTICE 'PASS DB05: adjacent booking accepted';

    BEGIN
        INSERT INTO booking.bookings VALUES (
            'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
            '90000000-0000-4000-8000-000000000005',
            '11111111-1111-4111-8111-111111111111',
            '2099-01-02 10:00:00+00',
            '2099-01-02 10:00:00+00',
            'confirmed'
        );
        RAISE EXCEPTION 'FAIL: zero-length booking accepted';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'PASS DB06: zero-length booking rejected';
    END;

    PERFORM set_config(
        'app.tenant_id', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', true
    );

    IF EXISTS (
        SELECT 1 FROM booking.bookings
        WHERE id = '90000000-0000-4000-8000-000000000002'
    ) THEN
        RAISE EXCEPTION 'FAIL: tenant B reads tenant A booking';
    END IF;
    RAISE NOTICE 'PASS DB07: cross-tenant booking read hidden';

    UPDATE booking.bookings SET status = 'cancelled'
    WHERE id = '90000000-0000-4000-8000-000000000002';
    IF FOUND THEN
        RAISE EXCEPTION 'FAIL: cross-tenant update succeeded';
    END IF;
    RAISE NOTICE 'PASS DB08: cross-tenant update affects zero rows';

    DELETE FROM booking.bookings
    WHERE id = '90000000-0000-4000-8000-000000000002';
    IF FOUND THEN
        RAISE EXCEPTION 'FAIL: cross-tenant delete succeeded';
    END IF;
    RAISE NOTICE 'PASS DB09: cross-tenant delete affects zero rows';

    PERFORM set_config(
        'app.tenant_id', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true
    );

    IF NOT EXISTS (
        SELECT 1 FROM booking.bookings
        WHERE id = '90000000-0000-4000-8000-000000000002'
          AND status = 'confirmed'
    ) THEN
        RAISE EXCEPTION 'FAIL: original booking changed';
    END IF;
    RAISE NOTICE 'PASS DB10: original booking remains unchanged';
END
$test$;

ROLLBACK;
SELECT 'DB TEST TRANSACTION ROLLED BACK' AS result;