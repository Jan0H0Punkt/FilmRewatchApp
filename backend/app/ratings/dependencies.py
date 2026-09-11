"""FastAPI dependency providers for the ratings module (DESIGN §5.1, M1 PR4).

Wires the layer chain for injection: request-scoped session →
:class:`RatingRepository` → :class:`RatingService`. The film flows depend on
:func:`get_rating_service` (service-to-service, §5.1); FastAPI caches
``get_session`` per request, so every module's repository shares the one
session — the film create's single atomic unit of work (FR-LIB-03).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.ratings.repository import RatingRepository
from app.ratings.service import RatingService


def get_rating_repository(
    session: Annotated[Session, Depends(get_session)],
) -> RatingRepository:
    """Repository bound to the request's session."""
    return RatingRepository(session)


def get_rating_service(
    repository: Annotated[RatingRepository, Depends(get_rating_repository)],
) -> RatingService:
    """Service over the request's repository (the film flows' seam, and PR7's)."""
    return RatingService(repository)
