\set ON_ERROR_STOP on
BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Runtime role is deliberately not an owner or superuser.
-- Login credentials will be provisioned separately.
CREATE ROLE lab03_app
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS;

REVOKE ALL ON DATABASE booking_lab FROM PUBLIC;
GRANT CONNECT ON DATABASE booking_lab TO lab03_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE SCHEMA booking AUTHORIZATION lab03_owner;
GRANT USAGE ON SCHEMA booking TO lab03_app;

CREATE TABLE booking.tenants (
    id uuid PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE booking.professionals (
    tenant_id uuid NOT NULL REFERENCES booking.tenants(id),
    id uuid NOT NULL,
    name text NOT NULL,
    PRIMARY KEY (tenant_id, id)
);

CREATE TABLE booking.bookings (
    tenant_id uuid NOT NULL REFERENCES booking.tenants(id),
    id uuid NOT NULL,
    professional_id uuid NOT NULL,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'cancelled')),
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, professional_id)
        REFERENCES booking.professionals(tenant_id, id),
    CHECK (
        isfinite(starts_at) AND isfinite(ends_at)
        AND starts_at < ends_at
    ),
    CONSTRAINT no_overlapping_confirmed_bookings
        EXCLUDE USING gist (
            tenant_id WITH =,
            professional_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status = 'confirmed')
);

CREATE TABLE booking.idempotency (
    tenant_id uuid NOT NULL REFERENCES booking.tenants(id),
    user_id uuid NOT NULL,
    key text NOT NULL CHECK (length(key) BETWEEN 1 AND 128),
    request_hash text NOT NULL,
    booking_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id, key),
    FOREIGN KEY (tenant_id, booking_id)
        REFERENCES booking.bookings(tenant_id, id)
);

-- Synthetic fixtures only.
INSERT INTO booking.tenants VALUES
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Synthetic Salon A'),
    ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Synthetic Salon B');

INSERT INTO booking.professionals VALUES
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     '11111111-1111-4111-8111-111111111111', 'Professional A'),
    ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '22222222-2222-4222-8222-222222222222', 'Professional B');

ALTER TABLE booking.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking.tenants FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_boundary ON booking.tenants
    TO lab03_app
    USING (
        id = nullif(current_setting('app.tenant_id', true), '')::uuid
    )
    WITH CHECK (
        id = nullif(current_setting('app.tenant_id', true), '')::uuid
    );

ALTER TABLE booking.professionals ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking.professionals FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_boundary ON booking.professionals
    TO lab03_app
    USING (
        tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    );

ALTER TABLE booking.bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking.bookings FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_boundary ON booking.bookings
    TO lab03_app
    USING (
        tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    );

ALTER TABLE booking.idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking.idempotency FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_boundary ON booking.idempotency
    TO lab03_app
    USING (
        tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
        AND user_id = nullif(current_setting('app.user_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
        AND user_id = nullif(current_setting('app.user_id', true), '')::uuid
    );

GRANT SELECT ON booking.tenants, booking.professionals TO lab03_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON booking.bookings TO lab03_app;
GRANT SELECT, INSERT ON booking.idempotency TO lab03_app;

COMMIT;

SELECT current_database(), current_user;

SELECT rolname, rolsuper, rolbypassrls, rolcanlogin
FROM pg_roles
WHERE rolname = 'lab03_app';

SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'booking'
ORDER BY tablename;