"""Pydantic request/response schemas for the ratings module (DESIGN §5.3, M1 PR4).

The read shape of one rating event, embedded in the film detail projection's
``rating_history`` (REQ §7.3 Section B) and reused by the PR7 rating endpoints.
The create shape lives with its flow: the film create payload's mandatory
``first_rating`` (FR-LIB-03) is defined in ``app/films/schemas.py``; PR7 adds
the standalone one.
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field

from app.core.schemas import StrictSchema


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
