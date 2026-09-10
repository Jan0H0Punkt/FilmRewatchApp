"""FastAPI dependency providers for the genres module (DESIGN §5.1, M1 PR3).

Wires the layer chain for injection into the routes: request-scoped session →
:class:`GenreRepository` → :class:`GenreService`. The router only ever depends
on the service (a router never imports a repository).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.genres.repository import GenreRepository
from app.genres.service import GenreService


def get_genre_repository(session: Annotated[Session, Depends(get_session)]) -> GenreRepository:
    """Repository bound to the request's session."""
    return GenreRepository(session)


def get_genre_service(
    repository: Annotated[GenreRepository, Depends(get_genre_repository)],
) -> GenreService:
    """Service over the request's repository (also the seam M1 PR4+ film flows
    reuse service-to-service, and tests override)."""
    return GenreService(repository)
