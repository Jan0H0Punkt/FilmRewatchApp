"""Presentation layer for the genres module (DESIGN §5.1, M1 PR3).

FastAPI routes under ``/api/v1/genres`` (mounted by the app factory). Exactly
one route: the read-only lookup backing genre autocomplete (FR-TAG-06 analogue,
FR-SF-07, §5.3). There is deliberately no create or delete endpoint — genres
are created implicitly through film payloads and die via orphan cleanup (§5.3).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.errors import error_responses
from app.genres.dependencies import get_genre_service
from app.genres.schemas import GenreRead
from app.genres.service import GenreService

router = APIRouter()


@router.get(
    "",
    summary="List genres",
    description=(
        "Read-only lookup for filtering and autocomplete (FR-TAG-06 analogue). "
        "Returns all genres alphabetically; `?prefix=` narrows to labels "
        "starting with the given text, case-insensitively."
    ),
    responses=error_responses({422: ["VALIDATION_ERROR"]}),
)
def list_genres(
    service: Annotated[GenreService, Depends(get_genre_service)],
    prefix: Annotated[
        str | None,
        Query(description="Case-insensitive name prefix to filter by (for autocomplete)."),
    ] = None,
) -> list[GenreRead]:
    return [GenreRead.model_validate(genre) for genre in service.list_by_prefix(prefix)]
