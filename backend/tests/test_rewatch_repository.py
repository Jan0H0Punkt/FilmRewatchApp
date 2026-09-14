"""Rewatch data access against a real Postgres (DESIGN §9).

The ``db_session`` fixture auto-marks these as ``db``; everything rolls back at
teardown.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.db import utc_now
from app.films.models import Film, Title
from app.ratings.models import RatingEntry
from app.rewatch.algorithm import DueFilm
from app.rewatch.repository import RewatchRepository

COMPUTED_AT: datetime = utc_now()


def _add_film(
    session: Session, *, natural_key: str, delay_days: int = 0, favorite: bool = False
) -> Film:
    film = Film(
        natural_key=natural_key,
        release_year=1995,
        director="Michael Mann",
        runtime_minutes=170,
        poster_image=None,
        is_favorite=favorite,
        delay_days=delay_days,
    )
    session.add(film)
    # The id default is applied at flush, not at construction, so the FK below
    # needs a real value to point at.
    session.flush()
    session.add(Title(film_id=film.id, value=natural_key, is_primary=True, is_original=True))
    return film


def test_collect_inputs_averages_only_the_rated_watches(db_session: Session) -> None:
    film = _add_film(db_session, natural_key="heat|1995|michael mann")
    db_session.add(RatingEntry(film_id=film.id, value=Decimal("4.0"), watch_date=date(2024, 1, 1)))
    db_session.add(RatingEntry(film_id=film.id, value=Decimal("5.0"), watch_date=date(2025, 1, 1)))
    # An unrated watch (FR-RAT-12): it counts as a watch but not toward the mean.
    db_session.add(RatingEntry(film_id=film.id, value=None, watch_date=date(2026, 1, 1)))
    db_session.commit()

    [row] = RewatchRepository(db_session).collect_inputs()

    assert row.film_id == film.id
    assert row.average_rating == Decimal("4.5")
    assert row.watch_count == 3
    assert row.last_watched_date == date(2026, 1, 1)


def test_collect_inputs_reports_a_wholly_unrated_film_as_none(db_session: Session) -> None:
    film = _add_film(
        db_session, natural_key="solaris|1972|andrei tarkovsky", delay_days=7, favorite=True
    )
    db_session.add(RatingEntry(film_id=film.id, value=None, watch_date=date(2026, 2, 2)))
    db_session.commit()

    [row] = RewatchRepository(db_session).collect_inputs()

    assert row.average_rating is None
    assert row.watch_count == 1
    assert row.delay_days == 7
    assert row.is_favorite is True


def test_replace_all_stores_the_given_order_as_position(db_session: Session) -> None:
    first = _add_film(db_session, natural_key="a|1990|a")
    second = _add_film(db_session, natural_key="b|1990|b")
    db_session.commit()
    repository = RewatchRepository(db_session)

    repository.replace_all(
        [
            DueFilm(film_id=second.id, days_until_next_rewatch=-40),
            DueFilm(film_id=first.id, days_until_next_rewatch=0),
        ],
        COMPUTED_AT,
    )
    repository.commit()

    stored = list(repository.list_all())
    assert [row.film_id for row in stored] == [second.id, first.id]
    assert [row.position for row in stored] == [0, 1]
    assert [row.days_until_next_rewatch for row in stored] == [-40, 0]


def test_replace_all_leaves_no_rows_from_the_previous_run(db_session: Session) -> None:
    stale = _add_film(db_session, natural_key="stale|1990|a")
    fresh = _add_film(db_session, natural_key="fresh|1990|b")
    db_session.commit()
    repository = RewatchRepository(db_session)

    repository.replace_all([DueFilm(film_id=stale.id, days_until_next_rewatch=-1)], COMPUTED_AT)
    repository.commit()
    repository.replace_all([DueFilm(film_id=fresh.id, days_until_next_rewatch=-2)], COMPUTED_AT)
    repository.commit()

    assert [row.film_id for row in repository.list_all()] == [fresh.id]


def test_an_empty_run_clears_the_projection(db_session: Session) -> None:
    film = _add_film(db_session, natural_key="gone|1990|a")
    db_session.commit()
    repository = RewatchRepository(db_session)
    repository.replace_all([DueFilm(film_id=film.id, days_until_next_rewatch=0)], COMPUTED_AT)
    repository.commit()

    repository.replace_all([], COMPUTED_AT)
    repository.commit()

    assert list(repository.list_all()) == []


def test_deleting_a_film_removes_its_suggestion(db_session: Session) -> None:
    # The FK cascade keeps the projection from outliving the film between runs.
    film = _add_film(db_session, natural_key="doomed|1990|a")
    db_session.commit()
    repository = RewatchRepository(db_session)
    repository.replace_all([DueFilm(film_id=film.id, days_until_next_rewatch=0)], COMPUTED_AT)
    repository.commit()

    db_session.delete(film)
    db_session.commit()

    assert list(repository.list_all()) == []


def test_collect_inputs_is_empty_for_an_empty_library(db_session: Session) -> None:
    assert RewatchRepository(db_session).collect_inputs() == []
