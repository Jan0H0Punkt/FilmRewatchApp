"""Letterboxd data access against a real Postgres (DESIGN §9). Rolls back per test."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.letterboxd.models import LetterboxdEntry


def _add_film(session: Session, title: str, year: int, letterboxd_url: str | None = None) -> Film:
    film = Film(
        natural_key=f"{title.lower()}|{year}|someone",
        release_year=year,
        director="Someone",
        runtime_minutes=100,
        letterboxd_url=letterboxd_url,
    )
    session.add(film)
    session.flush()
    session.add(Title(film_id=film.id, value=title, is_primary=True, is_original=False))
    session.flush()
    return film


def _entry(guid: str = "letterboxd-watch-1", **overrides: object) -> LetterboxdEntry:
    fields: dict[str, object] = {
        "guid": guid,
        "film_title": "Heat",
        "film_year": 1995,
        "film_url": "https://letterboxd.com/film/heat/",
        "watched_date": date(2026, 9, 1),
        "rating": Decimal("4.0"),
        "rewatch": False,
    }
    fields.update(overrides)
    return LetterboxdEntry(**fields)


def test_deleting_the_suggested_film_keeps_the_entry_without_a_suggestion(
    db_session: Session,
) -> None:
    film = _add_film(db_session, "Heat", 1995)
    entry = _entry(suggested_film_id=film.id)
    db_session.add(entry)
    db_session.flush()

    db_session.delete(film)
    db_session.flush()
    db_session.refresh(entry)

    assert entry.suggested_film_id is None
    assert entry.resolved_at is None
