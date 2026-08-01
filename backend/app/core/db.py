"""Database session & SQLAlchemy plumbing (DESIGN §5.2, §3.1 data-access layer).

This is M0 **plumbing only**: a SQLAlchemy 2.x engine built from ``DATABASE_URL``
(DESIGN §3.5 / §8), a session factory, the request-scoped session dependency the
repositories (M1) will depend on, and the typed declarative :class:`Base` every
ORM model inherits from.

**No domain tables are defined here.** The seven §5.2 tables and their first
migration arrive in M1, so ``Base.metadata`` is empty in M0 — which is exactly
what makes ``alembic revision --autogenerate`` produce an empty diff against a
migrated database (M0 PR4 acceptance).

The engine and session factory are created lazily and cached, so importing this
module never requires the database to be configured or reachable; the connection
is opened on first use.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for every ORM model (SQLAlchemy 2.x ``Mapped[...]``).

    Models (M1+) subclass this so their columns are visible to the strict type
    checker (DESIGN §5.7) and their tables register on ``Base.metadata`` for
    Alembic autogeneration.
    """


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp default (REQ §4.1 ISO-8601 UTC timestamps)."""
    return datetime.now(UTC)


@lru_cache
def get_engine() -> Engine:
    """Build the process-wide engine from ``DATABASE_URL`` once (DESIGN §3.5)."""
    settings = get_settings()
    # ``pool_pre_ping`` transparently recovers a stale connection if the laptop's
    # Postgres container was restarted between requests (DESIGN §8.2).
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    """Return the cached session factory bound to :func:`get_engine`."""
    # ``expire_on_commit=False`` keeps committed ORM instances usable while a
    # router serialises them into the response — the common FastAPI pattern.
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI request-scoped session dependency (DESIGN §5.1 data-access).

    Yields a session for the lifetime of one request and always closes it.
    Routers never use this directly — the repositories (M1) depend on it, keeping
    business logic free of session lifecycle concerns.
    """
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
