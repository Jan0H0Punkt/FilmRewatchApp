"""Presentation layer for the stats module (DESIGN §5.1) — the single ``/api/v1/stats`` route."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.stats.dependencies import get_stats_service
from app.stats.schemas import StatsRead
from app.stats.service import StatsService

router = APIRouter()


@router.get(
    "",
    summary="Viewing statistics",
    description=(
        "All-time statistics plus one block per calendar year, from the earliest "
        "dated watch through the current year, **newest year first**. Watches "
        "recorded as 'seen before, date unknown' count in the all-time block only. "
        "An empty library is a normal answer: zeros and no years."
    ),
)
def get_stats(service: Annotated[StatsService, Depends(get_stats_service)]) -> StatsRead:
    return StatsRead.from_stats(service.stats(date.today()))
