# Publishing ESK-LAB-03 to GitHub

Recommended repo name: `eskelsen-multitenant-booking-security-lab`
Owner: your authorized GitHub account (e.g. `r3eskelsen`).

**Public description:**

> FastAPI + PostgreSQL multitenant booking demo with RLS tenant isolation,
> conflict-safe reservations, idempotency and recorded functional tests.

1. Create a new **public** repository without automatically adding README,
   `.gitignore` or license. This project already includes all three.
2. Upload the **contents** of `01_GITHUB_UPLOAD` to repository root. Include
   hidden `.env.example`, `.gitignore`, and `.github/workflows/`. Do **not**
   upload the containing delivery folder, private reconstruction script or
   `02_UPWORK_PORTFOLIO` / `03_VERIFICATION_AND_INSTRUCTIONS`.
3. Keep `.env`, `data/`, caches, local generated output and production
   credentials private.
4. Check that `README.md`, `src/`, `scripts/`, `tests/`, `docs/`,
   `evidence/`, `.github/`, `compose.yaml`, and `LICENSE` appear at root.
5. A green static CI workflow confirms **only syntax and manifest hashes**.
   To independently validate the runtime, follow the isolated Docker
   instructions and run the original test suites.
6. Commit title: `Publish ESK-LAB-03 booking security demo v1.0.1`

Repository topics: `python`, `fastapi`, `postgresql`, `row-level-security`,
`multi-tenant`, `booking-system`, `concurrency`, `idempotency`, `docker`, `testing`.

The README's SVG/PNG artwork is illustrative. No live protected dashboard
or real customer records are shown.
