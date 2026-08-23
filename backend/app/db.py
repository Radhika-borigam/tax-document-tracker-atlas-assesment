"""Database setup: a single SQLite file and a session helper.

SQLite is chosen so a reviewer can run the project with nothing to install.
The rest of the code only depends on SQLAlchemy, so moving to Postgres later
is a connection-string change, not a rewrite.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# The DB lives next to the backend package unless overridden (tests use in-memory
# or a temp file via DATABASE_URL).
DEFAULT_DB = f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(__file__)), 'accountant.db')}"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DB)

# check_same_thread=False is the standard SQLite + FastAPI setting.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
# expire_on_commit defaults to True on purpose: after a commit, cached relationship
# collections (client.requirements, requirement.documents) reload on next access,
# so re-derivation and matching always see fresh data.
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables. Safe to call repeatedly."""
    from app import models  # noqa: F401  (import registers the models)

    Base.metadata.create_all(bind=engine)
