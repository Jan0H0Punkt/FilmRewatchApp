"""Presentation layer for the tags module (DESIGN §5.1, M1 PR3).

FastAPI routes under ``/api/v1/tags`` (mounted by the app factory). Exactly one
route: the read-only lookup backing tag autocomplete (FR-TAG-06 backend half,
§5.3). There is deliberately no create or delete endpoint — tags are created
implicitly through film payloads and die via orphan cleanup (§5.3).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.errors import error_responses
from app.tags.dependencies import get_tag_service
from app.tags.schemas import TagRead
from app.tags.service import TagService

router = APIRouter()


@router.get(
    "",
    summary="List tags",
    description=(
        "Read-only lookup for filtering and autocomplete (FR-TAG-06). "
        "Returns all tags alphabetically; `?prefix=` narrows to labels starting "
        "with the given text, case-insensitively."
    ),
    responses=error_responses({422: ["VALIDATION_ERROR"]}),
)
def list_tags(
    service: Annotated[TagService, Depends(get_tag_service)],
    prefix: Annotated[
        str | None,
        Query(description="Case-insensitive name prefix to filter by (for autocomplete)."),
    ] = None,
) -> list[TagRead]:
    return [TagRead.model_validate(tag) for tag in service.list_by_prefix(prefix)]
