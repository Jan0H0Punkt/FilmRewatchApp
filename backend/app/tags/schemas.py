"""Pydantic request/response schemas for the tags module (DESIGN §5.3, M1 PR3).

Only a read shape exists: tags are created implicitly through film payloads
(FR-TAG-01) and die via orphan cleanup, so there is no request schema here.
"""

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from app.core.schemas import StrictSchema


class TagRead(StrictSchema):
    """One tag row as served by the ``GET /tags`` lookup (REQ §4.3 fields)."""

    # Merged into the strict base config: allows building the schema straight
    # from the ORM row while the model stays strict and closed.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
