"""Business-logic layer for the ratings module (DESIGN §5.1, M1 PR4).

The PR4 slice of the rating rules: persisting a film's entries and serving the
history projection (FR-RAT-05/06). The film create flow calls
:meth:`RatingService.add_entry` service-to-service for the mandatory first
rating (FR-LIB-03); the standalone lifecycle — ``POST /films/{id}/ratings``,
``DELETE /ratings/{id}`` and the last-rating rule — arrives in PR7.

Value/date validation (0.5-5.0 in 0.5 steps, no future ``watch_date``) is
enforced at the API boundary by the strict schemas (§5.4, NFR-INT-03).
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.ratings.models import RatingEntry


class RatingRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1).

    Satisfied structurally by :class:`~app.ratings.repository.RatingRepository`
    and by the in-memory fakes the service unit tests inject (§9).
    """

    def add(self, entry: RatingEntry) -> None: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]: ...


class RatingService:
    """Rating business rules over an injected repository interface."""

    def __init__(self, repository: RatingRepositoryProtocol) -> None:
        self._repository = repository

    def add_entry(self, film_id: uuid.UUID, value: Decimal, watch_date: date) -> RatingEntry:
        """Record one rating event for a film (REQ §4.2).

        Same-day repeats are allowed (FR-RAT-04). The entry joins the caller's
        unit of work — the film create flow commits it atomically with the film
        (FR-LIB-03).
        """
        entry = RatingEntry(film_id=film_id, value=value, watch_date=watch_date)
        self._repository.add(entry)
        return entry

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]:
        """The film's history, most recent first (FR-RAT-05/06)."""
        return self._repository.list_for_film(film_id)
