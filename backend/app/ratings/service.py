"""Business-logic layer for the ratings module (DESIGN §5.1, M1 PR4/PR7).

The PR4 slice of the rating rules: persisting a film's entries and serving the
history projection (FR-RAT-05/06). The film create flow calls
:meth:`RatingService.add_entry` service-to-service for the mandatory first
rating (FR-LIB-03). PR7 adds the standalone lifecycle's rating-side rules —
the no-future-``watch_date`` domain check and rating-not-found — consumed
service-to-service by :class:`~app.films.service.FilmService`, which owns the
``POST /films/{id}/ratings`` / ``DELETE /ratings/{id}`` orchestration (it
already depends one-way on this service; the reverse would be circular).

Value-shape validation (0.5-5.0 in 0.5 steps) is enforced at the API boundary
by the strict schemas (§5.4, NFR-INT-03); the future-``watch_date`` rule is a
*domain* rule with its own stable error code, so it lives here instead.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol

from fastapi import status

from app.core.errors import AppError
from app.ratings.models import RatingEntry


class FutureWatchDateError(AppError):
    """A ``watch_date`` in the future (FR-RAT-03) — its own stable code, not
    the generic ``VALIDATION_ERROR`` a schema-level check would produce."""

    code = "FUTURE_WATCH_DATE"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = "watch_date must not be in the future."


class RatingNotFoundError(AppError):
    """No rating entry with the requested id (rendered as ``NOT_FOUND``)."""

    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND
    message = "Rating not found."

    def __init__(self, rating_id: uuid.UUID) -> None:
        super().__init__(f"Rating {rating_id} not found.")


class RatingRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1).

    Satisfied structurally by :class:`~app.ratings.repository.RatingRepository`
    and by the in-memory fakes the service unit tests inject (§9).
    """

    def add(self, entry: RatingEntry) -> None: ...

    def find_by_id(self, rating_id: uuid.UUID) -> RatingEntry | None: ...

    def count_for_film(self, film_id: uuid.UUID) -> int: ...

    def delete(self, entry: RatingEntry) -> None: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]: ...


class RatingService:
    """Rating business rules over an injected repository interface."""

    def __init__(self, repository: RatingRepositoryProtocol) -> None:
        self._repository = repository

    def add_entry(self, film_id: uuid.UUID, value: Decimal, watch_date: date) -> RatingEntry:
        """Record one rating event for a film (REQ §4.2).

        Same-day repeats are allowed (FR-RAT-04). The entry joins the caller's
        unit of work — the film create flow commits it atomically with the film
        (FR-LIB-03); the standalone add-rating flow (PR7) commits it via
        :class:`~app.films.service.FilmService.add_rating`.

        The future-``watch_date`` check is defence in depth for the create
        flow (the ``FirstRatingCreate`` schema already rejects it before this
        is ever called) and the sole enforcement point for the standalone
        endpoint, whose schema deliberately leaves this rule to the service so
        it can raise the dedicated :class:`FutureWatchDateError`.
        """
        if watch_date > datetime.now(UTC).date():
            raise FutureWatchDateError()
        entry = RatingEntry(film_id=film_id, value=value, watch_date=watch_date)
        self._repository.add(entry)
        return entry

    def get_or_raise(self, rating_id: uuid.UUID) -> RatingEntry:
        """A rating by id, or :class:`RatingNotFoundError` (PR7)."""
        entry = self._repository.find_by_id(rating_id)
        if entry is None:
            raise RatingNotFoundError(rating_id)
        return entry

    def count_for_film(self, film_id: uuid.UUID) -> int:
        """How many ratings a film currently has — the FR-RAT-07 last-rating
        check, asked by :class:`~app.films.service.FilmService.delete_rating`."""
        return self._repository.count_for_film(film_id)

    def delete(self, entry: RatingEntry) -> None:
        """Stage a rating's removal in the caller's unit of work (PR7)."""
        self._repository.delete(entry)

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]:
        """The film's history, most recent first (FR-RAT-05/06)."""
        return self._repository.list_for_film(film_id)
