"""Shared pytest fixtures for all feature tests.

Approach (documented):
- DB: a single file-backed SQLite engine shared across the process (StaticPool
  so the in-memory/connection is reused). `Base.metadata.create_all` builds the
  schema. `db_session` is function-scoped and wraps each test in a transaction
  that is rolled back at the end, so tests stay isolated.
- Auth in tests: rather than driving Redis-backed sessions, the role fixtures
  (`as_manager`/`as_waiter`/`as_cashier`/`as_chef`) override the `current_staff`
  FastAPI dependency to return the proper domain `Staff` object. This avoids any
  Redis dependency in unit/endpoint tests. `client` only overrides `get_db`.
- Celery is forced into eager mode (no broker) via CELERY_TASK_ALWAYS_EAGER=1,
  set before any task module import.
"""
import os

os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"
# Session middleware is Redis-backed; default to a locally reachable Redis so
# session-roundtrip tests work (the app default host "redis" is docker-only).
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infra.db import Base
import app.infra.models  # noqa: F401  (register tables on Base.metadata)

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)

Base.metadata.create_all(_engine)


@pytest.fixture()
def db_session():
    """Function-scoped session; rolled back and cleaned after each test."""
    connection = _engine.connect()
    txn = connection.begin()
    session = _TestSession(bind=connection)
    try:
        yield session
    finally:
        session.close()
        txn.rollback()
        connection.close()


@pytest.fixture()
def seeded(db_session):
    """db_session with seed data (staff, menu, tables) committed in-transaction."""
    from app.infra.seed import seed

    seed(db_session)
    db_session.commit()
    return db_session


@pytest.fixture(autouse=True)
def _fresh_session_store():
    """Give the Redis-backed session store a fresh async connection per test.

    The store caches one redis.asyncio connection bound to the event loop that
    first used it; each TestClient spins its own loop, so a shared connection
    raises 'Event loop is closed' on the second test. Re-creating it per test
    keeps the connection bound to the current loop.
    """
    from redis.asyncio.client import Redis

    from app.config import settings
    from app.main import _store

    _store._connection = Redis.from_url(settings.REDIS_URL)
    yield


@pytest.fixture()
def client(db_session):
    """TestClient with get_db overridden to the test session."""
    from fastapi.testclient import TestClient

    from app.deps import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login(client, code, password):
    """Helper: POST /login with form credentials, returns the response."""
    return client.post(
        "/login",
        data={"code": code, "password": password},
        follow_redirects=False,
    )


def _staff_client(db_session, staff_class, code, name):
    from fastapi.testclient import TestClient

    from app.deps import current_staff, get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_staff] = lambda: staff_class(code, name)
    return TestClient(app), app


@pytest.fixture()
def as_manager(db_session):
    from app.domain.staff import Manager

    c, app = _staff_client(db_session, Manager, "M01", "Sardor")
    yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def as_waiter(db_session):
    from app.domain.staff import Waiter

    c, app = _staff_client(db_session, Waiter, "W01", "Aziz")
    yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def as_cashier(db_session):
    from app.domain.staff import Cashier

    c, app = _staff_client(db_session, Cashier, "K01", "Lola")
    yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def as_chef(db_session):
    from app.domain.staff import Chef

    c, app = _staff_client(db_session, Chef, "C01", "Bek")
    yield c
    app.dependency_overrides.clear()
