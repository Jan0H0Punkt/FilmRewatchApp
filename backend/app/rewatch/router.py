"""Presentation layer for the rewatch module (DESIGN §5.1, §5.8).

The single route under ``/api/v1/rewatch-suggestions`` (mounted by the app
factory). It serves the stored projection, which the service recomputes on the
day's first read (§5.8). There is no write route and no refresh route: reading
is the only thing that drives a run.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.rewatch.dependencies import get_rewatch_service
from app.rewatch.schemas import RewatchSuggestionRead
from app.rewatch.service import RewatchService

router = APIRouter()


@router.get(
    "",
    summary="List rewatch suggestions",
    description=(
        "The latest daily-computed due-list (FR-RW-03/04/05): the films that "
        "are due or overdue for a rewatch, **most overdue first**. Not-yet-due "
        "films are omitted, so `days_until_next_rewatch` is always `<= 0` — "
        "`0` means due today. The order is the algorithm's own and must not be "
        "re-sorted by the client (FR-RW-04). The list is recomputed at most once "
        "a day, on the first request of the day. An empty list is a normal "
        "answer, not an error (FR-RW-06)."
    ),
)
def list_rewatch_suggestions(
    service: Annotated[RewatchService, Depends(get_rewatch_service)],
) -> list[RewatchSuggestionRead]:
    return [
        RewatchSuggestionRead.model_validate(row) for row in service.list_suggestions(date.today())
    ]
