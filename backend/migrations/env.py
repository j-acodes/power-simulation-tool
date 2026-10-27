"""Alembic environment: migrates the database ``DATABASE_URL`` names.

The app calls ``backend.models.upgrade_to_head`` at startup, which hands its
own engine in through ``config.attributes``. Run from the command line
(``alembic upgrade head``, ``alembic revision --autogenerate -m "..."``), the
engine is built from ``DATABASE_URL`` instead.
"""

from alembic import context

from backend.models import Base, make_engine

engine = context.config.attributes.get("engine") or make_engine()

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
