# Results and provenance

- **Original isolated execution:** 37 functional checks PASS in saved evidence.
- **Fresh reconstruction of an earlier verified review ZIP:** 37 functional checks PASS using fresh PostgreSQL storage and rebuilt runtime image; deployment identities and port adapted.
- Breakdown: **10 database** + **23 HTTP / concurrency** + **4 application-role / connection pool**.
- Concurrent booking: 12 requests for overlapping intervals -> one accepted, eleven conflicts.
- Concurrent same-key idempotency: 12 requests -> one booking, eleven replays.
- 40 alternating tenant transactions on a single reused backend without context leakage.
- **Independent publication-only checks:** ZIP SHA-256, file hashes, Python syntax and YAML parsing PASS; see delivery verification report.

These are controlled functional test results, **not** throughput benchmarking,
production certification, or independent penetration testing.

**Not independently rerun on this publication package:** Docker-backed live tests,
HTTP authentication, database RLS tests, the 37-case suite and full reconstruction.

**Not performed:** production deployment, comprehensive secrets/log audit,
backup/recovery test, dependency vulnerability/license audit.

See `evidence/` for source run output, including test IDs and observed results.
The original machine-specific reconstruction script was kept out of GitHub
because it uses private absolute paths and an earlier source ZIP.
