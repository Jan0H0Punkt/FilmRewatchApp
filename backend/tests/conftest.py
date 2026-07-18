"""Shared environment + Postgres-backed test harness (DESIGN §9, M1 PR2).

Two concerns live here:

1. **Offline app construction.** Building the FastAPI app (``create_app``)
   loads settings, which require ``DATABASE_URL`` (DESIGN §3.5). Offline tests
   never open a connection — the engine is created lazily — so a placeholder
   URL is enough to construct the app without a database. ``setdefault``
   leaves a real value from the environment intact.

2. **The §9 repository-test harness.** Repository tests run against a *real*
   Postgres: a dedicated, disposable ``filmrewatch_test`` database on the
   composed server (never the dev ``filmrewatch`` data), dropped and recreated
   once per session and migrated to ``head`` through the real Alembic chain.
   Each test runs inside an outer transaction that is rolled back afterwards
   (savepoint mode, so ``session.commit()`` inside a test stays isolated) —
   tests are order-independent. Tests using :func:`db_session` /
   :func:`db_engine` are auto-marked ``db`` (see ``pyproject.toml``); when the
   database is unreachable they **skip with a reason** instead of erroring, so
   the offline subset (``pytest -m "not db"``) always runs cleanly.

The harness talks to the loopback-published composed Postgres
(``docker compose up postgres``); point ``TEST_DATABASE_URL`` at another
server to override — that database is *owned by the suite* and gets dropped.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")

from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_BACKEND_DIR = Path(__file__).resolve().parents[1]

# Defaults mirror docker-compose.yml (loopback-published port, default
# credentials) with the dedicated test database swapped in.
_DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://filmrewatch:filmrewatch@127.0.0.1:5432/filmrewatch_test"
)

# Tests requesting either fixture are DB-bound and get the `db` marker
# auto-applied in `pytest_collection_modifyitems` — forgetting the marker
# cannot silently move a repository test into the offline subset.
_DB_FIXTURES = frozenset({"db_engine", "db_session"})


def _test_database_url() -> URL:
    """The suite-owned test database URL (``TEST_DATABASE_URL`` overrides)."""
    return make_url(os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DATABASE_URL))


@cache
def _database_unreachable_reason() -> str | None:
    """Probe the test server once per run; a reason string means "skip".

    Probes the maintenance ``postgres`` database (always present) rather than
    the test database, which may not exist until the harness creates it.
    """
    probe = create_engine(
        _test_database_url().set(database="postgres"),
        poolclass=NullPool,
        connect_args={"connect_timeout": 2},
    )
    try:
        with probe.connect():
            return None
    except OperationalError:
        return (
            "Postgres is not reachable at "
            f"{_test_database_url().render_as_string()} — DB-bound tests need the "
            "composed database (`docker compose up postgres`); the offline subset "
            'runs with `pytest -m "not db"`.'
        )
    finally:
        probe.dispose()


def _recreate_test_database(test_url: URL) -> None:
    """Drop and recreate the disposable test database (clean slate per run)."""
    database = test_url.database
    assert database is not None
    admin = create_engine(
        test_url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    try:
        with admin.connect() as connection:
            # FORCE (Postgres 13+) evicts stale connections from a crashed run.
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
            connection.execute(text(f'CREATE DATABASE "{database}"'))
    finally:
        admin.dispose()


def _migrate_to_head(test_url: URL) -> None:
    """Run the real Alembic chain against the test database.

    ``migrations/env.py`` reads ``DATABASE_URL`` via the cached
    :func:`get_settings` (never ``alembic.ini``), so the override goes through
    that same channel: swap the environment variable, clear the cache, and
    restore both afterwards so no other test sees the test-database settings.
    """
    config = AlembicConfig(str(_BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    previous = os.environ["DATABASE_URL"]  # always set — see the top of this file
    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    get_settings.cache_clear()
    try:
        command.upgrade(config, "head")
    finally:
        os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-mark every test that uses the Postgres harness as ``db``."""
    for item in items:
        if isinstance(item, pytest.Function) and _DB_FIXTURES & set(item.fixturenames):
            item.add_marker(pytest.mark.db)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Session-scoped engine onto a freshly migrated test database (§9).

    Skips (with a reason) when the composed Postgres is down, so the offline
    subset never errors on an unreachable database.
    """
    reason = _database_unreachable_reason()
    if reason is not None:
        pytest.skip(reason)
    test_url = _test_database_url()
    _recreate_test_database(test_url)
    _migrate_to_head(test_url)
    engine = create_engine(test_url, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Per-test isolated ORM session: everything rolls back at teardown.

    The session joins an outer transaction in ``create_savepoint`` mode — a
    ``session.commit()`` inside a test only releases a savepoint, so even
    committed rows vanish when the outer transaction rolls back. Repository
    tests are therefore order-independent (§9).
    """
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def clear_settings_cache() -> Iterator[None]:
    """Isolate a test that overrides settings (REVIEW_M0 §7.4 interplay).

    :func:`get_settings` is ``lru_cache``d, so without this a test overriding
    e.g. an environment variable would silently read the previously cached
    ``Settings`` — and leak its own override to later tests. Clearing before
    *and* after gives the test a fresh read and takes it back out.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
