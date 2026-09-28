"""Letterboxd matching and sync against a real Postgres (REQ §5.7). Rolls back per test."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.films.schemas import FilmUpdate
from app.letterboxd.errors import EntryNotFoundError, EntryResolvedError
from app.letterboxd.feed import FeedEntry
from app.letterboxd.models import LetterboxdEntry
from app.letterboxd.repository import LetterboxdRepository
from app.letterboxd.service import LetterboxdService, match_film, run_sync
from app.ratings.models import RatingEntry

TODAY = date(2026, 9, 28)


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


def _feed_entry(
    guid: str,
    title: str = "Heat",
    year: int = 1995,
    slug: str = "heat",
    watched: date = date(2026, 9, 20),
    rating: Decimal | None = Decimal("4.0"),
) -> FeedEntry:
    return FeedEntry(
        guid=guid,
        film_title=title,
        film_year=year,
        film_slug=slug,
        watched_date=watched,
        rating=rating,
        rewatch=False,
    )


def _queued(session: Session) -> list[LetterboxdEntry]:
    return list(session.scalars(select(LetterboxdEntry).order_by(LetterboxdEntry.created_at)))


def _watch_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(RatingEntry)) or 0


# --- match_film ---------------------------------------------------------------


def test_link_match_beats_a_title_match(db_session: Session) -> None:
    linked = _add_film(db_session, "Heat (linked)", 1995, "https://letterboxd.com/film/heat/")
    _add_film(db_session, "Heat", 1995)

    assert match_film(LetterboxdRepository(db_session), "heat", "Heat", 1995) == linked.id


def test_title_match_when_no_link_matches(db_session: Session) -> None:
    film = _add_film(db_session, "Don't Worry Darling", 2022)

    found = match_film(
        LetterboxdRepository(db_session), "dont-worry-darling", "don't worry darling", 2022
    )
    assert found == film.id


def test_two_title_matches_are_no_match(db_session: Session) -> None:
    _add_film(db_session, "Godzilla", 1954)
    twin = _add_film(db_session, "Gojira", 1954)
    db_session.add(Title(film_id=twin.id, value="Godzilla", is_primary=False, is_original=False))
    db_session.flush()

    assert match_film(LetterboxdRepository(db_session), "godzilla", "Godzilla", 1954) is None


def test_no_slug_falls_through_to_the_title(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)

    assert match_film(LetterboxdRepository(db_session), None, "Heat", 1995) == film.id


# --- run_sync -----------------------------------------------------------------


def test_queues_new_entries_with_a_suggestion_and_writes_no_watch(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)

    queued = run_sync(
        LetterboxdRepository(db_session),
        [_feed_entry("g2"), _feed_entry("g1", title="Unknown", slug="unknown")],
        TODAY,
    )

    assert queued == 2
    rows = _queued(db_session)
    assert [(row.guid, row.suggested_film_id) for row in rows] == [("g2", film.id), ("g1", None)]
    assert rows[0].film_url == "https://letterboxd.com/film/heat/"
    assert rows[0].rating == Decimal("4.0")
    assert _watch_count(db_session) == 0


def test_an_unrated_entry_is_queued_unrated(db_session: Session) -> None:
    run_sync(LetterboxdRepository(db_session), [_feed_entry("g1", rating=None)], TODAY)

    assert _queued(db_session)[0].rating is None


def test_stops_at_a_known_guid(db_session: Session) -> None:
    repository = LetterboxdRepository(db_session)
    run_sync(repository, [_feed_entry("g1", slug="a", title="A")], TODAY)

    queued = run_sync(
        repository,
        [
            _feed_entry("g3", slug="c", title="C"),
            _feed_entry("g1", slug="a", title="A"),
            _feed_entry("g0"),
        ],
        TODAY,
    )

    assert queued == 1
    assert [row.guid for row in _queued(db_session)] == ["g1", "g3"]


def test_running_twice_over_the_same_feed_queues_nothing_new(db_session: Session) -> None:
    repository = LetterboxdRepository(db_session)
    feed = [_feed_entry("g2", slug="b", title="B"), _feed_entry("g1", slug="a", title="A")]
    run_sync(repository, feed, TODAY)

    assert run_sync(repository, feed, TODAY) == 0
    assert len(_queued(db_session)) == 2


def test_stops_at_an_entry_whose_watch_is_already_in_the_app(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    db_session.add(RatingEntry(film_id=film.id, value=None, watch_date=date(2026, 9, 20)))
    db_session.flush()

    queued = run_sync(
        LetterboxdRepository(db_session),
        [
            _feed_entry("g3", slug="c", title="C"),
            _feed_entry("g2"),
            _feed_entry("g1", slug="a", title="A"),
        ],
        TODAY,
    )

    assert queued == 1
    assert [row.guid for row in _queued(db_session)] == ["g3"]


def test_a_future_entry_is_skipped_without_stopping(db_session: Session) -> None:
    queued = run_sync(
        LetterboxdRepository(db_session),
        [_feed_entry("g2", watched=date(2026, 9, 29)), _feed_entry("g1", slug="a", title="A")],
        TODAY,
    )

    assert queued == 1
    assert [row.guid for row in _queued(db_session)] == ["g1"]


def test_a_skipped_future_entry_is_queued_once_its_date_arrives(db_session: Session) -> None:
    repository = LetterboxdRepository(db_session)
    feed = [_feed_entry("g2", watched=date(2026, 9, 29)), _feed_entry("g1", slug="a", title="A")]
    run_sync(repository, feed, TODAY)

    assert run_sync(repository, feed, date(2026, 9, 29)) == 1
    assert {row.guid for row in _queued(db_session)} == {"g1", "g2"}


def test_suggestion_is_unset_for_an_unknown_film(db_session: Session) -> None:
    run_sync(LetterboxdRepository(db_session), [_feed_entry("g1")], TODAY)

    assert _queued(db_session)[0].suggested_film_id is None


# --- LetterboxdService ----------------------------------------------------------


class FakeFilms:
    """Records the FilmService calls; the real one is covered by the films tests."""

    def __init__(self, letterboxd_url: str | None = None) -> None:
        self.letterboxd_url = letterboxd_url
        self.ratings: list[tuple[uuid.UUID, Decimal | None, date]] = []
        self.updates: list[tuple[uuid.UUID, FilmUpdate]] = []

    def add_rating(self, film_id: uuid.UUID, value: Decimal | None, watch_date: date) -> object:
        self.ratings.append((film_id, value, watch_date))
        return object()

    def get_detail(self, film_id: uuid.UUID) -> object:
        url = self.letterboxd_url

        class Detail:
            letterboxd_url = url

        return Detail()

    def update(self, film_id: uuid.UUID, data: FilmUpdate) -> object:
        self.updates.append((film_id, data))
        return object()


def _service(
    session: Session, films: FakeFilms | None = None, feed: list[FeedEntry] | None = None
) -> LetterboxdService:
    return LetterboxdService(
        LetterboxdRepository(session),
        films or FakeFilms(),  # pyright: ignore[reportArgumentType] - structural fake
        lambda: feed or [],
        lambda: TODAY,
    )


def _open_entry(session: Session, guid: str = "g1", **overrides: object) -> LetterboxdEntry:
    fields: dict[str, object] = {
        "guid": guid,
        "film_title": "Heat",
        "film_year": 1995,
        "film_url": "https://letterboxd.com/film/heat/",
        "watched_date": date(2026, 9, 20),
        "rating": Decimal("4.5"),
        "rewatch": True,
    }
    fields.update(overrides)
    entry = LetterboxdEntry(**fields)
    session.add(entry)
    session.flush()
    return entry


def test_sync_runs_the_fetched_feed(db_session: Session) -> None:
    assert _service(db_session, feed=[_feed_entry("g1")]).sync() == 1


def test_list_open_carries_the_suggested_films_primary_title(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    _open_entry(db_session, suggested_film_id=film.id)
    _open_entry(
        db_session, "g2", film_title="Unknown", film_url="https://letterboxd.com/film/unknown/"
    )

    rows = _service(db_session).list_open()

    suggested = next(row for row in rows if row.film_title == "Heat").suggested_film
    assert suggested is not None and (suggested.id, suggested.title) == (film.id, "Heat")
    assert next(row for row in rows if row.film_title == "Unknown").suggested_film is None


def test_list_open_auto_resolves_an_entry_whose_watch_now_exists(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995, "https://letterboxd.com/film/heat/")
    entry = _open_entry(db_session)
    db_session.add(RatingEntry(film_id=film.id, value=Decimal("4.5"), watch_date=date(2026, 9, 20)))
    db_session.flush()

    assert _service(db_session).list_open() == []
    assert entry.resolved_at is not None


def test_list_open_uses_a_fresh_match_for_a_still_open_entry_of_the_same_film(
    db_session: Session,
) -> None:
    """Resolving A's film must also refresh B's suggestion, not just A's (§5.7)."""
    url = "https://letterboxd.com/film/unknown/"
    first = _open_entry(db_session, "g1", film_url=url, watched_date=date(2026, 9, 20))
    second = _open_entry(db_session, "g2", film_url=url, watched_date=date(2026, 9, 21))
    film = _add_film(db_session, "Unknown", 1995, url)
    db_session.add(
        RatingEntry(film_id=film.id, value=Decimal("4.5"), watch_date=first.watched_date)
    )
    db_session.flush()

    rows = _service(db_session).list_open()

    assert [row.id for row in rows] == [second.id]
    suggested = rows[0].suggested_film
    assert suggested is not None and (suggested.id, suggested.title) == (film.id, "Unknown")


def test_assign_adds_the_watch_and_resolves(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    entry = _open_entry(db_session)
    films = FakeFilms()

    _service(db_session, films).assign(entry.id, film.id)

    assert films.ratings == [(film.id, Decimal("4.5"), date(2026, 9, 20))]
    assert entry.resolved_at is not None


def test_assign_sets_the_letterboxd_url_only_when_the_film_has_none(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    first = _open_entry(db_session)
    second = _open_entry(db_session, "g2")

    empty = FakeFilms(letterboxd_url=None)
    _service(db_session, empty).assign(first.id, film.id)
    linked = FakeFilms(letterboxd_url="https://boxd.it/x")
    _service(db_session, linked).assign(second.id, film.id)

    assert [(film_id, data.letterboxd_url) for film_id, data in empty.updates] == [
        (film.id, "https://letterboxd.com/film/heat/")
    ]
    assert linked.updates == []


def test_assign_keeps_an_unrated_entry_unrated(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    entry = _open_entry(db_session, rating=None)
    films = FakeFilms()

    _service(db_session, films).assign(entry.id, film.id)

    assert films.ratings[0][1] is None


def test_dismiss_resolves_without_a_watch(db_session: Session) -> None:
    entry = _open_entry(db_session)
    films = FakeFilms()

    _service(db_session, films).dismiss(entry.id)

    assert entry.resolved_at is not None
    assert films.ratings == []


def test_acting_on_an_unknown_entry_is_not_found(db_session: Session) -> None:
    with pytest.raises(EntryNotFoundError):
        _service(db_session).dismiss(uuid.uuid4())


def test_acting_on_a_resolved_entry_is_rejected(db_session: Session) -> None:
    entry = _open_entry(db_session, resolved_at=datetime(2026, 9, 21, tzinfo=UTC))

    with pytest.raises(EntryResolvedError):
        _service(db_session).assign(entry.id, uuid.uuid4())
    with pytest.raises(EntryResolvedError):
        _service(db_session).dismiss(entry.id)
