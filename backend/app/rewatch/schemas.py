"""Pydantic response schemas for the rewatch module (DESIGN §5.3, §5.8).

Read-only: the projection is written by the daily job, never by a request, so
there is no request schema here.
"""

from uuid import UUID

from pydantic import ConfigDict

from app.core.schemas import StrictSchema


class RewatchSuggestionRead(StrictSchema):
    """One due film as served by ``GET /rewatch-suggestions`` (FR-RW-03).

    Deliberately carries no film metadata: the client already holds the whole
    library from ``GET /films`` and joins on ``film_id`` locally (§6.3).
    """

    # Merged into the strict base config: allows building the schema straight
    # from the ORM row while the model stays strict and closed.
    model_config = ConfigDict(from_attributes=True)

    film_id: UUID
    # ``0`` is due today; a negative value is overdue by that many days. Never
    # positive — not-yet-due films are omitted from the list entirely.
    days_until_next_rewatch: int
