"""Tests for the data-access plumbing (DESIGN §5.2, M0 PR4).

M0 ships the SQLAlchemy/Alembic *harness* with **no domain tables** — those are
M1. This guards that invariant at the model level: an empty ``Base.metadata`` is
what makes ``alembic revision --autogenerate`` produce an empty diff. It needs no
database (the engine is created lazily, on first use).
"""

from app.core.db import Base, get_session


def test_baseline_defines_no_tables() -> None:
    # No ORM models exist in M0, so the shared metadata must be empty.
    assert Base.metadata.tables == {}


def test_get_session_is_a_generator_dependency() -> None:
    # The FastAPI dependency is a generator (yields then cleans up); constructing
    # it must not touch the database.
    import inspect

    assert inspect.isgeneratorfunction(get_session)
