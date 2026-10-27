# Projects and designs are stored in Postgres, and the schema changes only by migration

The tool is moving to a shared company server, where several engineers' projects live in one
database. SQLite with wholesale schema creation served a single engineer: changing a model
meant deleting the database. On a shared server that would destroy other people's work. So
projects and designs are stored in Postgres, named by `DATABASE_URL`, and the schema is owned
by Alembic migrations in `backend/migrations/versions/`. The app applies any pending migration
at startup, so a deploy of new code always meets a matching schema. A model change without a
migration fails the test suite.

Only Postgres is supported, including for tests. Tests run against a disposable database
named `*_test` (`TEST_DATABASE_URL`), and the test setup refuses any other name, because each
run empties it. There is no default database URL: a missing `DATABASE_URL` stops the app
rather than quietly writing somewhere else.

Existing SQLite data was not carried over; the Postgres database starts empty.

## Considered Options

- **Keep SQLite until deployment.** This was the earlier position. It was rejected once the
  move to a company server became the immediate plan.
- **Support SQLite and Postgres side by side.** That would keep tests fast and
  install-free, but behaviour could differ between the database tested and the one deployed
  (timezones, foreign keys, JSON). Rejected in favour of testing on what runs in production.
- **Run migrations as a separate deploy step.** That gives more control over when a
  migration runs, but it adds a manual step for whoever deploys. Migrating at startup is
  simpler while the app runs as a single process. Revisit if it is ever scaled to several
  workers or replicas.
