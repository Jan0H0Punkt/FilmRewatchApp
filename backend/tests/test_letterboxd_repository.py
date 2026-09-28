"""Letterboxd data access against a real Postgres (DESIGN §9). Rolls back per test."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.db import utc_now
from app.films.models import Film, Title
from app.letterboxd.models import LetterboxdEntry
from app.letterboxd.repository import LetterboxdRepository
from app.ratings.models import RatingEntry


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


def test_is_known_guid(db_session: Session) -> None:
    db_session.add(_entry("letterboxd-watch-7"))
    db_session.flush()
    repository = LetterboxdRepository(db_session)

    assert repository.is_known_guid("letterboxd-watch-7")
    assert not repository.is_known_guid("letterboxd-watch-8")


def test_film_ids_by_slug_matches_every_letterboxd_url_shape_but_not_a_longer_slug(
    db_session: Session,
) -> None:
    exact = _add_film(db_session, "Heat", 1995, "https://letterboxd.com/film/heat")
    _add_film(db_session, "Heat 2", 2026, "https://letterboxd.com/film/heat-2/")
    _add_film(db_session, "Short", 2000, "https://boxd.it/heat")

    assert LetterboxdRepository(db_session).film_ids_by_slug("heat") == [exact.id]


def test_film_ids_by_title_year_searches_every_title_case_insensitively(
    db_session: Session,
) -> None:
    pulse = _add_film(db_session, "回路", 2001)
    db_session.add(Title(film_id=pulse.id, value=" Pulse ", is_primary=False, is_original=False))
    _add_film(db_session, "Pulse", 2006)
    db_session.flush()

    assert LetterboxdRepository(db_session).film_ids_by_title_year("pulse", 2001) == [pulse.id]


def test_has_watch_on(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    db_session.add(RatingEntry(film_id=film.id, value=None, watch_date=date(2026, 9, 1)))
    db_session.flush()
    repository = LetterboxdRepository(db_session)

    assert repository.has_watch_on(film.id, date(2026, 9, 1))
    assert not repository.has_watch_on(film.id, date(2026, 9, 2))


def test_list_open_skips_resolved_entries_newest_watch_first(db_session: Session) -> None:
    db_session.add(_entry("a", watched_date=date(2026, 9, 1)))
    db_session.add(_entry("b", watched_date=date(2026, 9, 5)))
    db_session.add(_entry("c", watched_date=date(2026, 9, 9), resolved_at=utc_now()))
    db_session.flush()

    assert [entry.guid for entry in LetterboxdRepository(db_session).list_open()] == ["b", "a"]


def test_primary_titles(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)

    assert LetterboxdRepository(db_session).primary_titles({film.id}) == {film.id: "Heat"}
