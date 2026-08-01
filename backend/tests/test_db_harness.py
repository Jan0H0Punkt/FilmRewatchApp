"""Tests for the Postgres-backed repository-test harness itself (§9, M1 PR2).

The sample round-trip below is the template every M1 repository test builds on:
request ``db_session`` and read/write real rows. The two "isolation" tests
insert the *same* unique ``natural_key`` and ``commit()`` — they can only both
pass (in either order) if each test's work is rolled back afterwards, which is
exactly the per-test isolation the harness promises.

These tests are auto-marked ``db`` (they use the harness fixtures) and skip
with a reason when the composed Postgres is down.
"""

import uuid

import pytest
from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title

# Deliberately shared by both isolation tests — see the module docstring.
_ISOLATION_KEY = "harness isolation probe|1927|fritz lang"


def _make_film(natural_key: str) -> Film:
    return Film(
        id=uuid.uuid4(),
        natural_key=natural_key,
        release_year=1927,
        director="Fritz Lang",
    )


def test_migrated_schema_has_the_seven_domain_tables(db_engine: Engine) -> None:
    # The session fixture ran the real Alembic chain (not create_all): the §5.2
    # tables plus Alembic's own bookkeeping table must exist.
    assert set(inspect(db_engine).get_table_names()) == {
        "films",
        "titles",
        "rating_entries",
        "tags",
        "film_tags",
        "genres",
        "film_genres",
        "alembic_version",
    }


def test_round_trip_persists_and_reads_back(db_session: Session) -> None:
    film = _make_film("metropolis|1927|fritz lang")
    db_session.add(film)
    db_session.add(Title(film_id=film.id, value="Metropolis", is_primary=True, is_original=True))
    db_session.commit()

    loaded = db_session.scalars(
        select(Film).where(Film.natural_key == "metropolis|1927|fritz lang")
    ).one()
    assert loaded.director == "Fritz Lang"
    assert loaded.created_at is not None
    title = db_session.scalars(select(Title).where(Title.film_id == loaded.id)).one()
    assert title.value == "Metropolis"
    assert title.is_primary


def test_isolation_same_key_first(db_session: Session) -> None:
    db_session.add(_make_film(_ISOLATION_KEY))
    db_session.commit()


def test_isolation_same_key_second(db_session: Session) -> None:
    # Would raise IntegrityError (unique natural_key) if the sibling test's
    # committed row had survived its teardown rollback.
    db_session.add(_make_film(_ISOLATION_KEY))
    db_session.commit()


@pytest.mark.db
def test_explicit_marker_still_works(db_session: Session) -> None:
    # The marker may also be written out; auto-marking must not conflict.
    assert db_session.scalars(select(Film)).all() == []
