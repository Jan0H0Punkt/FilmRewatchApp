"""FastAPI dependency providers for the stats module (DESIGN §5.1)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.stats.repository import StatsRepository
from app.stats.service import StatsService


def get_stats_repository(session: Annotated[Session, Depends(get_session)]) -> StatsRepository:
    """Repository bound to the request's session."""
    return StatsRepository(session)


def get_stats_service(
    repository: Annotated[StatsRepository, Depends(get_stats_repository)],
) -> StatsService:
    """Service over the request's repository (the seam tests override)."""
    return StatsService(repository)
