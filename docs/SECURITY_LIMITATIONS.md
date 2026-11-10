# Security limitations and responsible use

**NOT production ready, NOT independently security certified, and NOT a full
enterprise identity system.** This sample uses entirely synthetic fixtures.

- Only two built-in identities are accepted in the local JWT subject registry.
- There is no registration, password authentication, MFA, user provisioning,
  revocation, rate limiting, rotating signing key, or external IdP.
- Anyone who knows the laboratory JWT signing secret can issue lab tokens.
- Per-transaction PostgreSQL custom GUC isolation assumes trusted application
  code and protected credentials: it is not protection against arbitrary SQL
  executed with the same application role.
- DB owner/admin credentials exist only in local `.env`, created by the
  initializer. Treat `.env` and Docker environment inspect output as secrets.
- The runtime uses mutable upstream image tags (no immutable digests) and
  a version-pinned Python package list without per-wheel hash locks.
- No TLS, production perimeter, WAF, abuse defenses, external secret manager,
  central logging or distributed tracing is included.
- No full backup/restore, failover, penetration test, licensed-dependency audit
  or sustained load test was conducted for this publication package.
- Client role vs administrator role and recurring schedule management are
  deliberately out of scope.

The public code and evidence must not be used with real customers, payment
records, live secrets or client information without separate engineering and
security reviews.
