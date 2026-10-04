"""Pytest fixtures.

Per tech.md, integration tests use a REAL PostgreSQL database via testcontainers
(never SQLite). The `db` fixture spins up a Postgres container for the test
session and provides a clean session per test. The `client` fixture provides a
FastAPI TestClient wired to the test database with a fake PaymentProvider.

Model metadata is created directly from SQLAlchemy's Base.metadata here so the
harness works before/independently of Alembic; the Alembic migration itself is
verified separately in task 2.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from app.core.db import Base, get_db
from app.core.ratelimit import limiter
from app.main import create_app

# Import all models so Base.metadata is fully populated (task 2 adds them).
try:  # pragma: no cover - models land in task 2
    import app.models  # noqa: F401
except Exception:  # pragma: no cover
    pass


@pytest.fixture(scope="session")
def pg_engine() -> Generator[Engine, None, None]:
    """Start one PostgreSQL container for the whole test session."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        engine = create_engine(url, future=True)
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()


@pytest.fixture
def db(pg_engine: Engine) -> Generator[Session, None, None]:
    """Provide a clean session per test (truncate all tables between tests)."""
    maker = sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False, future=True)
    session = maker()
    try:
        yield session
    finally:
        session.rollback()
        # Clean every table so tests are isolated.
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Generator[None, None, None]:
    """Clear slowapi's in-memory counters before each test.

    The ``limiter`` is a module-level singleton with in-process storage, so its
    per-key counters otherwise leak across tests in the same session. Once the
    cumulative number of logins (or public booking posts) exceeds a route's
    limit, later tests get spurious 429s (and the follow-up admin calls get 401
    because no auth cookie was set). Resetting between tests keeps each test's
    rate-limit budget independent.
    """
    try:
        limiter.reset()
    except Exception:  # pragma: no cover - storage may not support reset
        pass
    yield


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient using the test DB session."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
