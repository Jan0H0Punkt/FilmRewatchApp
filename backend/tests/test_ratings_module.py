"""Tests for the ratings module's PR4 slice (FR-RAT-04..06, §9).

The persistence primitives the film flows consume: the service constructing
entries into the caller's unit of work (offline, against a fake repository)
and the repository's history ordering against real Postgres — most recent
``watch_date`` first, same-day repeats (allowed, FR-RAT-04) tie-broken by
``created_at`` descending. The standalone rating endpoints arrive in PR7.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.films.models import Film
from app.ratings.models import RatingEntry
from app.ratings.repository import RatingRepository
from app.ratings.service import RatingService

# --------------------------------------------------------------------------- #
# Service — offline, against a fake repository (§9)
# --------------------------------------------------------------------------- #


class FakeRatingRepository:
    """In-memory :class:`RatingRepositoryProtocol` implementation."""

    def __init__(self) -> None:
        self.entries: list[RatingEntry] = []

    def add(self, entry: RatingEntry) -> None:
        self.entries.append(entry)

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]:
        return [entry for entry in self.entries if entry.film_id == film_id]


def test_service_stages_an_entry_with_the_given_fields() -> None:
    repository = FakeRatingRepository()
    service = RatingService(repository)
    film_id = uuid.uuid4()

    entry = service.add_entry(film_id, Decimal("3.5"), date(2026, 1, 1))

    assert repository.entries == [entry]
    assert entry.film_id == film_id
    assert entry.value == Decimal("3.5")
    assert entry.watch_date == date(2026, 1, 1)
    assert [listed.id for listed in service.list_for_film(film_id)] == [entry.id]


# --------------------------------------------------------------------------- #
# Repository ordering — real Postgres via the PR2 harness (§9)
# --------------------------------------------------------------------------- #


def test_history_is_most_recent_first_with_same_day_repeats(db_session: Session) -> None:
    film = Film(
        id=uuid.uuid4(),
        natural_key="rating order probe|2001|jane doe",
        release_year=2001,
        director="Jane Doe",
    )
    db_session.add(film)
    db_session.flush()

    repository = RatingRepository(db_session)
    # Inserted out of order; the two 2026-01-05 entries are a same-day repeat
    # (FR-RAT-04) — flushed separately so their created_at values order them.
    first_of_the_day = RatingEntry(
        film_id=film.id, value=Decimal("2.0"), watch_date=date(2026, 1, 5)
    )
    repository.add(first_of_the_day)
    db_session.flush()
    older = RatingEntry(film_id=film.id, value=Decimal("3.0"), watch_date=date(2026, 1, 1))
    repository.add(older)
    db_session.flush()
    second_of_the_day = RatingEntry(
        film_id=film.id, value=Decimal("4.0"), watch_date=date(2026, 1, 5)
    )
    repository.add(second_of_the_day)
    db_session.flush()

    listed = repository.list_for_film(film.id)
    # Most recent watch_date first (FR-RAT-05/06); within the repeated day,
    # the most recently recorded entry leads.
    assert [entry.id for entry in listed] == [
        second_of_the_day.id,
        first_of_the_day.id,
        older.id,
    ]
