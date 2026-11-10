# LAB-03 test matrix

| Group | Cases | Recorded result | Evidence |
|---|---:|---|---|
| Database access and correctness | DB01–DB10 (10) | PASS in original and reconstruction | `evidence/db_checks.txt` |
| HTTP authentication, tenant boundaries, booking & concurrency | HTTP01–HTTP23 (23) | PASS in original and reconstruction | `evidence/http_checks.txt` |
| Application role and pool context reuse | POOL01–POOL04 (4) | PASS in original and reconstruction | `evidence/pool_checks.txt` |

## Representative scenarios

- No tenant context exposes zero tenant-owned rows.
- Forged tenant insert, cross-tenant read/update/delete are rejected or invisible.
- Same-professional booking overlap rejected; adjacent interval accepted.
- Missing, expired and invalid JWTs are rejected.
- Client-provided `tenant_id` rejected, foreign professional hidden.
- Changed idempotency payload rejected with conflict.
- Twelve overlapping requests yield 1 success and 11 booking conflicts.
- Twelve simultaneous same-key submissions create exactly one booking.
- Connection reuse and transaction rollback do not retain previous tenant context in recorded test.

Tests generate only synthetic records; HTTP cleanup cancels tracked bookings
and retains booking history. For exact commands see `README.md`.

### Verification limits

The static GitHub workflow checks syntax and manifest integrity only, *not*
these live database/application test scenarios. Original recorded results do
not imply the publication package has been deployed or retested end to end.
