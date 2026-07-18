"""FastAPI dependency providers for the films module (DESIGN §5.1, M1 PR4).

Wires the film service and its collaborators for injection into the routes:
request-scoped session → :class:`FilmRepository` → :class:`FilmService`, with
the tag, genre, and rating services injected **service-to-service** (§5.1).
FastAPI caches ``get_session`` per request, so every module's repository
shares the one session — which is what makes the create flow a single atomic
unit of work (FR-LIB-03, NFR-INT-02).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.films.repository import FilmRepository
from app.films.service import FilmService
from app.genres.dependencies import get_genre_service
from app.genres.service import GenreService
from app.ratings.dependencies import get_rating_service
from app.ratings.service import RatingService
from app.tags.dependencies import get_tag_service
from app.tags.service import TagService


def get_film_repository(session: Annotated[Session, Depends(get_session)]) -> FilmRepository:
    """Repository bound to the request's session."""
    return FilmRepository(session)


def get_film_service(
    repository: Annotated[FilmRepository, Depends(get_film_repository)],
    tags: Annotated[TagService, Depends(get_tag_service)],
    genres: Annotated[GenreService, Depends(get_genre_service)],
    ratings: Annotated[RatingService, Depends(get_rating_service)],
) -> FilmService:
    """The film service over its repository and peer services."""
    return FilmService(repository, tags, genres, ratings)
