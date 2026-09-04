"""Delete the local SQLite DB so it can be recreated empty by
``Base.metadata.create_all`` at the next app startup.

Why this exists: ``designs.technology`` (added by the design-technology
feature — see docs/adr/0002-technology-declared-not-derived.md) is a
non-nullable column, and this project has no migration mechanism
(``backend/models.py`` builds the schema wholesale with
``Base.metadata.create_all``, no Alembic). There is therefore no way to add
the column to a database that already has rows in ``designs`` — the file has
to be deleted and rebuilt from scratch, which loses every project and
design in it.

This script never deletes anything silently: it prints what it is about to
destroy (the file path, and the project/design counts inside it, if it's
readable) and requires the exact string "yes" typed at a prompt before it
removes the file. Ctrl-C or anything else aborts with nothing changed.

Usage:
    python scripts/reset_db.py                # targets ./powertool.db (the default)
    DATABASE_URL=sqlite:///other.db python scripts/reset_db.py

Only handles a local ``sqlite:///`` file, matching ``make_engine``'s default
in backend/models.py. A non-sqlite DATABASE_URL (e.g. Postgres) is out of
scope for this script — it exits without touching anything.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


def _db_path_from_url(url: str) -> Path | None:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    return Path(url[len(prefix) :])


def _describe_contents(path: Path) -> str:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            designs = conn.execute("SELECT COUNT(*) FROM designs").fetchone()[0]
            return f"{projects} project(s), {designs} design(s)"
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return f"could not read contents ({exc})"


def main() -> int:
    url = os.environ.get("DATABASE_URL", "sqlite:///powertool.db")
    path = _db_path_from_url(url)
    if path is None:
        print(f"DATABASE_URL ({url!r}) is not a local sqlite file — this script only " "handles sqlite:///, doing nothing.")
        return 1

    if not path.exists():
        print(f"{path} does not exist already — nothing to delete. It will be created " "empty the next time the app starts.")
        return 0

    print(f"About to permanently delete: {path.resolve()}")
    print(f"Contents: {_describe_contents(path)}")
    print(
        "This destroys every project and design stored in it. There is no "
        "migration mechanism in this project, so this is required before "
        "the design.technology column can be added — see "
        "docs/adr/0002-technology-declared-not-derived.md."
    )
    answer = input('Type "yes" to permanently delete this file: ')
    if answer.strip() != "yes":
        print("Aborted — nothing was deleted.")
        return 1

    path.unlink()
    print(f"Deleted {path}. It will be recreated empty (schema only, no rows) the next " "time the app starts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
