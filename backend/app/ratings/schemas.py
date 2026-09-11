"""Pydantic request/response schemas for the ratings module (DESIGN §5.3, M1 PR4/PR7).

The read shape of one rating event, embedded in the film detail projection's
``rating_history`` (REQ §7.3 Section B) and reused by the PR7 rating endpoints.
The film create payload's mandatory ``first_rating`` (FR-LIB-03) is defined in
``app/films/schemas.py``, since it lives inside ``FilmCreate``; PR7 adds the
standalone create payload (``RatingCreate``, for ``POST /films/{id}/ratings``)
and the delete-outcome shape (``RatingDeletionResult``, for
``DELETE /ratings/{id}``) here.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.core.schemas import JsonDate, JsonDecimal, JsonUUID, StrictSchema


class RatingEntryRead(StrictSchema):
    """One rating event as served to the client (REQ §4.2, §7.3 Section B).

    ``value`` is a JSON number on the wire, so the field is a lax ``float``
    (the ORM hands the schema a ``Decimal``, which strict ``float`` would
    reject); values are halves, exactly float-representable.
    """

    # Merged into the strict base config: allows building the schema straight
    # from the ORM row while the model stays strict and closed.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    value: Annotated[float, Field(strict=False)]
    watch_date: date
    created_at: datetime


class RatingCreate(StrictSchema):
    """The ``POST /films/{id}/ratings`` payload — a new rating event (FR-RAT-01/02).

    ``watch_date`` is deliberately **not** checked against the future here —
    that business rule is a service-layer domain check (:class:`~app.ratings.
    service.FutureWatchDateError`, its own stable code) rather than the
    generic ``VALIDATION_ERROR`` a schema-level check would produce. The
    step/range rule *is* schema-level: it is a shape constraint, not a domain
    rule, so an off-step value yields plain ``VALIDATION_ERROR``.
    """

    value: JsonDecimal
    watch_date: JsonDate

    @field_validator("value")
    @classmethod
    def _value_in_half_steps(cls, value: JsonDecimal) -> JsonDecimal:
        # FR-RAT-02: 0.5-5.0 in increments of 0.5.
        if not Decimal("0.5") <= value <= Decimal("5.0") or value % Decimal("0.5") != 0:
            raise ValueError("rating value must be between 0.5 and 5.0 in steps of 0.5")
        return value


class RatingDeletionResult(StrictSchema):
    """The ``DELETE /ratings/{id}`` outcome (FR-RAT-07).

    Deleting a film's last remaining rating deletes the whole film (the §5.3
    invariant); ``film_deleted`` tells the two outcomes apart so the M3 UI
    knows whether to stay on the film or navigate away from it.
    """

    rating_id: JsonUUID
    film_id: JsonUUID
    film_deleted: bool
