# The tool stays on SQLite until it is deployed, and moving to Postgres brings Alembic with it

Persistence stays a single local SQLite file for as long as the tool runs on one engineer's
machine. The move to Postgres is deferred, not rejected: the trigger is deployment to a
company server, and it is deliberately bundled with adopting Alembic, because the two stop
being separable the moment someone else's designs are in the database.

This is worth recording because the code gives no hint that a move is coming. Nothing in
`backend/` mentions Postgres, `scripts/reset_db.py` handles SQLite only and says so, and the
persistence layer looks finished — which it is, for now.

## What the move actually costs

The application code is already portable and should stay that way. There is no raw SQL, no
SQLite-specific feature in use, and `make_engine` reads `DATABASE_URL` at call time. A
reader auditing this before the move should find that it still holds; if it no longer does,
that is the regression, not the missing driver. The known work, small:

- A Postgres driver in `requirements.txt` and the Dockerfile.
- `pool_pre_ping=True` on the engine, so the app survives the database restarting under it.
- `DateTime` → `DateTime(timezone=True)` on all four timestamp columns. The values written
  are already timezone-aware; SQLite stores them as text and does not care, Postgres would
  silently drop the offset into a `TIMESTAMP WITHOUT TIME ZONE`. This is itself a schema
  change, so it wants to be part of the first migration rather than a later one.
- `scripts/reset_db.py` needs a Postgres path or a successor. It unlinks a file today.

The large part is Alembic. On SQLite, a schema change is answered by deleting the file — see
`scripts/reset_db.py` and the startup guard `backend.models.check_schema`, which exists
precisely because that answer is silent otherwise. That answer is only tolerable because the
only data at risk belongs to the person making the change. On a shared server it is not
available at all, so Postgres does not merely permit migrations, it requires them, and every
subsequent column becomes a written migration instead of a reset.

## Considered Options

**Move to Postgres now, before deployment.** The code swap works today and would be honest
about the eventual target. Rejected because it buys nothing while the tool is single-user —
it adds a service to run locally (and Docker is not installed on the development machine),
and it would pull Alembic forward into a period where deleting the database is still the
correct, cheapest answer to a schema change. Deployment is in any case blocked on the IT
department's guidance about authentication, so the deadline is not ours to set.

**Move to Postgres now, keep resetting instead of migrating.** Rejected as the worst of
both: the operational weight of a database server with none of the safety that justifies it.

**Keep SQLite in production too.** Not seriously considered for a multi-user server, but
worth naming: SQLite would survive a handful of concurrent editors, and the optimistic
locking in `PUT /api/designs/{id}` is at the application layer, not the database's. What
rules it out is operations rather than concurrency — a file on a container's disk is nobody's
backup responsibility, whereas a company-hosted database usually already is.

## Consequences

**The test suite will test a different database than production runs.** `tests/conftest.py`
points `DATABASE_URL` at a temporary SQLite file. Nothing in the code touches a difference
between the two engines today, so this is an accepted drift rather than an unnoticed one; it
becomes a real gap the first time a query is written that is not plain SQLAlchemy Core.

**Two questions belong in the same conversation with IT**, alongside authentication: whether
they offer a managed Postgres, and whether it is backed up. A managed, backed-up instance
makes this a configuration change. Self-hosting the database means also owning its backups,
which is a materially larger job than the one described above.

**This partly answers the export/backup question, and should not be mistaken for answering
it fully.** `powertool.db` is currently gitignored, unbacked-up and unexportable, and a
backed-up Postgres removes the disaster-recovery half of that. It does not remove the other
half: moving one design between machines, or keeping a copy that outlives the company
server, still needs an export path.

**Until this happens, `scripts/reset_db.py` remains the migration mechanism.** Treat a reset
as part of any schema change, not as a follow-up someone will remember.
