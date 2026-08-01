"""Tests for the Postgres-backed repository-test harness itself (§9)."""

import uuid

import pytest
from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title

# Shared on purpose: the two isolation tests must collide if teardown ever
# stops rolling back.
_ISOLATION_KEY = "harness isolation probe|1927|fritz lang"


def _make_film(natural_key: str) -> Film:
    """A film row with only the DB-required columns — no title, genre, tag or rating.

    Invalid per FR-LIB-01/03, but those are service-layer rules; the database
    accepts it, and these tests exercise the harness, not the domain.
    """
    return Film(
        id=uuid.uuid4(),
        natural_key=natural_key,
        release_year=1927,
        director="Fritz Lang",
    )


def test_migrated_schema_has_the_seven_domain_tables(db_engine: Engine) -> None:
    # The fixture ran the real Alembic chain, not create_all.
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
    """The template repository tests copy: request ``db_session``, read/write real rows."""
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
