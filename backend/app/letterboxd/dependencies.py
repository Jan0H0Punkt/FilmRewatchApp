"""FastAPI dependency providers for the letterboxd module (DESIGN §5.1)."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.films.dependencies import get_film_service
from app.films.service import FilmService
from app.letterboxd.errors import LetterboxdDisabledError
from app.letterboxd.feed import FeedEntry, fetch_feed
from app.letterboxd.repository import LetterboxdRepository
from app.letterboxd.service import LetterboxdService


def get_letterboxd_repository(
    session: Annotated[Session, Depends(get_session)],
) -> LetterboxdRepository:
    """Repository bound to the request's session (shared with ``FilmService``)."""
    return LetterboxdRepository(session)


def get_feed_fetcher() -> Callable[[], list[FeedEntry]]:
    """The configured member's feed; raises :class:`LetterboxdDisabledError` without one (FR-LBX-01)."""
    username = get_settings().letterboxd_username

    def fetch() -> list[FeedEntry]:
        if not username:
            raise LetterboxdDisabledError()
        return fetch_feed(username)

    return fetch


def get_letterboxd_service(
    repository: Annotated[LetterboxdRepository, Depends(get_letterboxd_repository)],
    films: Annotated[FilmService, Depends(get_film_service)],
    fetch: Annotated[Callable[[], list[FeedEntry]], Depends(get_feed_fetcher)],
) -> LetterboxdService:
    """The review-list service (the seam tests override)."""
    return LetterboxdService(repository, films, fetch)
