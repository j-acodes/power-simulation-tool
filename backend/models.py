"""SQLAlchemy models + engine/session wiring for Projects/Designs persistence.

No Alembic yet — ``Base.metadata.create_all`` runs at app startup. The engine
is built by a small factory (``make_engine``) that reads ``DATABASE_URL`` when
called rather than baking it in at import time, so tests can point it at a
tmp-file SQLite DB (see ``tests/conftest.py``) before ``backend.main`` (which
calls the factory once at module load) is ever imported.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class Design(Base):
    __tablename__ = "designs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # 'pv' | 'bess' | 'hybrid' — declared at creation, never edited in place (see
    # docs/adr/0002-technology-declared-not-derived.md). Validated at the Pydantic
    # layer (schemas.DesignCreate); stored as a plain string here, no DB-level enum.
    technology: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_edited_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


def make_engine(database_url: str | None = None) -> Engine:
    """Build the DB engine. Reads ``DATABASE_URL`` at call time, not import
    time, so tests can set the env var before the first call (see
    ``backend.main``, which calls this once at module load)."""
    url = database_url or os.environ.get("DATABASE_URL", "sqlite:///powertool.db")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


class SchemaOutOfDate(RuntimeError):
    """An existing database is missing columns the models declare."""


def check_schema(engine: Engine) -> None:
    """Refuse to start against a database whose tables predate the models.

    ``Base.metadata.create_all`` creates missing TABLES but never alters an
    existing one, and this project has no Alembic. So adding a column leaves
    an existing database silently short of it: the app reads rows without the
    column and behaves as though the feature were never built, while the whole
    test suite stays green because tests build their database from scratch.
    That failure is invisible to every automated check there is, which is why
    it is worth a startup check rather than a note telling someone to remember.

    Raising here converts a silent wrong-behaviour bug into a loud refusal that
    names the fix.
    """
    inspector = inspect(engine)
    missing: list[str] = []
    for name, table in Base.metadata.tables.items():
        if not inspector.has_table(name):
            continue  # create_all will make it; only EXISTING tables can drift.
        present = {c["name"] for c in inspector.get_columns(name)}
        missing += [f"{name}.{c.name}" for c in table.columns if c.name not in present]
    if missing:
        raise SchemaOutOfDate(
            "The database is missing columns the models declare: "
            + ", ".join(sorted(missing))
            + ". This project has no migrations, so the database has to be "
            "recreated: run `python scripts/reset_db.py` (it names what it "
            "will destroy and asks before deleting anything)."
        )


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
