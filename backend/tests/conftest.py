"""Test fixtures: a fresh in-memory database per test, seeded with Rivera.

Everything here runs the real service functions directly — no browser, no HTTP
server — which is what the brief asks for.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.seed import seed


@pytest.fixture()
def db():
    # In-memory SQLite; StaticPool keeps it alive across the single connection.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """The Rivera household in its January state (Luis with one employer)."""
    return seed(db)
