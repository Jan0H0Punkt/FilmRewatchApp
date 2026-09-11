"""Tests for the ratings module's PR4/PR7 slices (FR-RAT-01..08, §9).

The persistence primitives the film flows consume: the service constructing
entries into the caller's unit of work (offline, against a fake repository)
and the repository's history ordering against real Postgres — most recent
``watch_date`` first, same-day repeats (allowed, FR-RAT-04) tie-broken by
``created_at`` descending. PR7 adds this module's half of the standalone
rating lifecycle — the ``FutureWatchDateError`` domain check and the
``get_or_raise``/``count_for_film``/``delete`` primitives ``FilmService``
consumes for ``POST /films/{id}/ratings`` and ``DELETE /ratings/{id}`` — plus
the ``RatingCreate``/``RatingDeletionResult`` schema rules. The end-to-end
route behaviour (envelope, last-rating-deletes-the-film) is exercised in
``test_films_api.py``, alongside the rest of the film flows.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.films.models import Film
from app.ratings.models import RatingEntry
from app.ratings.repository import RatingRepository
from app.ratings.schemas import RatingCreate
from app.ratings.service import FutureWatchDateError, RatingNotFoundError, RatingService

# --------------------------------------------------------------------------- #
# Service — offline, against a fake repository (§9)
# --------------------------------------------------------------------------- #


class FakeRatingRepository:
    """In-memory :class:`RatingRepositoryProtocol` implementation."""

    def __init__(self) -> None:
        self.entries: list[RatingEntry] = []

    def add(self, entry: RatingEntry) -> None:
        self.entries.append(entry)

    def find_by_id(self, rating_id: uuid.UUID) -> RatingEntry | None:
        return next((entry for entry in self.entries if entry.id == rating_id), None)

    def count_for_film(self, film_id: uuid.UUID) -> int:
        return len([entry for entry in self.entries if entry.film_id == film_id])

    def delete(self, entry: RatingEntry) -> None:
        self.entries = [row for row in self.entries if row.id != entry.id]

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
# PR7 — the standalone rating lifecycle's service-layer rules
# --------------------------------------------------------------------------- #


def test_add_entry_rejects_a_future_watch_date_with_its_own_domain_code() -> None:
    # FR-RAT-03: its own stable code, not the generic VALIDATION_ERROR a
    # schema-level check would produce — this is the sole enforcement point
    # for the standalone endpoint (RatingCreate deliberately doesn't check it).
    repository = FakeRatingRepository()
    service = RatingService(repository)
    tomorrow = datetime.now(UTC).date().replace(year=2999)

    with pytest.raises(FutureWatchDateError) as caught:
        service.add_entry(uuid.uuid4(), Decimal("4.0"), tomorrow)

    assert caught.value.code == "FUTURE_WATCH_DATE"
    assert caught.value.status_code == 422
    assert repository.entries == []


def test_get_or_raise_returns_the_entry_or_a_not_found_error() -> None:
    repository = FakeRatingRepository()
    service = RatingService(repository)
    entry = service.add_entry(uuid.uuid4(), Decimal("3.0"), date(2026, 1, 1))

    assert service.get_or_raise(entry.id) is entry

    with pytest.raises(RatingNotFoundError) as caught:
        service.get_or_raise(uuid.uuid4())
    assert caught.value.code == "NOT_FOUND"
    assert caught.value.status_code == 404


def test_count_for_film_reflects_only_that_films_entries() -> None:
    repository = FakeRatingRepository()
    service = RatingService(repository)
    film_id = uuid.uuid4()
    other_film_id = uuid.uuid4()

    assert service.count_for_film(film_id) == 0
    service.add_entry(film_id, Decimal("3.0"), date(2026, 1, 1))
    service.add_entry(film_id, Decimal("4.0"), date(2026, 1, 2))
    service.add_entry(other_film_id, Decimal("2.0"), date(2026, 1, 1))

    assert service.count_for_film(film_id) == 2
    assert service.count_for_film(other_film_id) == 1


def test_delete_stages_the_entrys_removal() -> None:
    repository = FakeRatingRepository()
    service = RatingService(repository)
    entry = service.add_entry(uuid.uuid4(), Decimal("3.0"), date(2026, 1, 1))

    service.delete(entry)

    assert repository.entries == []


# --------------------------------------------------------------------------- #
# PR7 — the RatingCreate schema (§5.4)
# --------------------------------------------------------------------------- #


def test_rating_create_enforces_the_half_step_range() -> None:
    for bad_value in (0.0, 0.4, 4.3, 5.5):
        with pytest.raises(ValidationError):
            RatingCreate.model_validate({"value": bad_value, "watch_date": "2026-01-01"})
    assert RatingCreate.model_validate({"value": 4.5, "watch_date": "2026-01-01"}).value == 4.5


def test_rating_create_does_not_reject_a_future_watch_date() -> None:
    # Deliberately schema-permissive: FUTURE_WATCH_DATE is a service-layer
    # domain check (contrast with FirstRatingCreate, which checks it in the
    # schema since the create flow has no other enforcement seam).
    created = RatingCreate.model_validate({"value": 4.5, "watch_date": "2999-01-01"})
    assert created.watch_date.isoformat() == "2999-01-01"


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
