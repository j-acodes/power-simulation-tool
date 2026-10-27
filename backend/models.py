"""SQLAlchemy models + engine/session wiring for Projects/Designs persistence.

The database is Postgres; its schema is owned by the Alembic migrations in
``backend/migrations/`` and brought up to date at app startup
(``upgrade_to_head``). The engine is built by a small factory (``make_engine``)
that reads ``DATABASE_URL`` when called rather than baking it in at import
time, so tests can point it at a disposable ``*_test`` database (see
``tests/conftest.py``) before ``backend.main`` (which calls the factory once at
module load) is ever imported.
"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, create_engine
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


def make_engine(database_url: str | None = None) -> Engine:
    """Build the DB engine. Reads ``DATABASE_URL`` at call time, not import
    time, so tests can set the env var before the first call (see
    ``backend.main``, which calls this once at module load).

    There is deliberately no default: a missing ``DATABASE_URL`` is a
    deployment mistake, and silently falling back to some local database would
    hide it until someone's work went missing."""
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Point it at a Postgres database, e.g. "
            "postgresql+psycopg://user:password@host:5432/powertool"
        )
    # pre_ping: a managed Postgres closes idle connections; check before use
    # rather than fail the first request after a quiet spell.
    return create_engine(url, pool_pre_ping=True)


_MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def alembic_config(engine: Engine):
    """Alembic config that runs ``backend/migrations`` against ``engine``."""
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS))
    config.attributes["engine"] = engine
    return config


def upgrade_to_head(engine: Engine) -> None:
    """Apply every migration the database has not had yet.

    Runs at startup, so a deploy of new code always meets a schema that matches
    it — the drift ``create_all`` used to allow (a new model column that an
    existing database never got) cannot happen."""
    from alembic import command

    command.upgrade(alembic_config(engine), "head")


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
