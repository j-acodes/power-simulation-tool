"""Point the backend at a disposable Postgres database before any test module
imports ``backend.main`` (which builds the engine once at module load, from
``DATABASE_URL``). pytest imports conftest.py before collecting test modules
in this directory, so this always wins over whatever ``DATABASE_URL`` the shell
has.

The tests need ``TEST_DATABASE_URL``, and refuse any database whose name does
not end in ``_test``: every run starts by dropping all its tables, so it must
never be able to reach a database that holds real projects.
"""

import os

from sqlalchemy import MetaData
from sqlalchemy.engine import make_url

_url = os.environ.get("TEST_DATABASE_URL")
if not _url:
    raise RuntimeError(
        "Set TEST_DATABASE_URL to a disposable Postgres database whose name ends "
        "in _test, e.g. postgresql+psycopg://postgres:password@localhost:5432/powertool_test"
    )
if not (make_url(_url).database or "").endswith("_test"):
    raise RuntimeError(
        f"TEST_DATABASE_URL names database {make_url(_url).database!r}; the tests drop "
        "every table in it, so they only run against a database named *_test."
    )
os.environ["DATABASE_URL"] = _url

# Start from empty, so the run also exercises every migration from scratch.
from backend.models import make_engine  # noqa: E402

_engine = make_engine(_url)
_existing = MetaData()
_existing.reflect(_engine)
_existing.drop_all(_engine)
_engine.dispose()
