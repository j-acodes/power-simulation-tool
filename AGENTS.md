# Agent guide

Start with the repository contract:

- Read [`CONTEXT.md`](CONTEXT.md) for domain vocabulary and modelling rules. Use its terms
  in code, tests, and UI copy.
- Read the accepted records in [`docs/adr/`](docs/adr/). ADR-0001 defines hybrid topology,
  ADR-0002 defines declared technology, and ADR-0004 defines ambient-rated transformer
  lookup. These decisions outrank older plans.
- For scoped work, read the matching spec under [`.scratch/`](.scratch/) before editing.
  Check its status and supersession notes; apply current acceptance criteria and keep
  unrelated cleanup out.
- For orientation or planning, read [`docs/project-status.md`](docs/project-status.md) for
  code-evidenced capabilities, deferred work, and historical context.
- Use the verification commands and runtime setup in the [README verification section](README.md#tests).
  The README is the entry point for running the app and its local data warning.

## Boundaries

The Python `powertool/` package is the sizing engine and electrical model. `backend/` is a
FastAPI adapter, persistence layer, and diagram-to-engine mapping. `frontend/` is a React +
TypeScript canvas and UI using React Flow and Zustand. Keep these boundaries: engine code
must not depend on web or UI modules; API schemas and diagram JSON are contracts; frontend
changes must preserve the API contract.

Component catalogues are YAML under `data/` and loaded into the in-memory database. SQLite
stores projects and designs; it is not the catalogue. Preserve the technology, topology,
declared-parameter, and ambient-rating decisions in the accepted ADRs when changing models.

## Data and verification

`DATABASE_URL` controls the database. Tests configure an isolated temporary SQLite database
(`tests/conftest.py`); keep that isolation. Frontend tests are Vitest tests; the existing Vite
test setup can start the backend, so use a disposable `DATABASE_URL` for verification and
never point it at a user's database.

`scripts/reset_db.py` deletes the selected SQLite database and all projects/designs. It is a
destructive schema-reset mechanism: inspect the target and obtain explicit user
authorization before running it. Do not use it as routine test setup.

Run the README checks appropriate to the affected behaviour; for docs-only work run link and
whitespace checks. Check failures are part of the report. Keep documentation aligned with
current code and accepted decisions; use repository sources rather than personal plans.
