"""Data-access layer for the letterboxd module (DESIGN §5.1, REQ §5.7).

Reads the films, titles and rating tables directly (as ``stats`` does) but
never writes them — watches are added through ``FilmService`` (FR-LBX-05/06).
"""

import uuid
from collections.abc import Collection
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.letterboxd.feed import film_slug
from app.letterboxd.models import LetterboxdEntry
from app.ratings.models import RatingEntry


class LetterboxdRepository:
    """SQLAlchemy-backed Letterboxd data access (one instance per session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def is_known_guid(self, guid: str) -> bool:
        statement = select(LetterboxdEntry.id).where(LetterboxdEntry.guid == guid)
        return self._session.scalar(statement) is not None

    def add(self, entry: LetterboxdEntry) -> None:
        self._session.add(entry)

    def get(self, entry_id: uuid.UUID) -> LetterboxdEntry | None:
        return self._session.get(LetterboxdEntry, entry_id)

    def list_open(self) -> list[LetterboxdEntry]:
        statement = (
            select(LetterboxdEntry)
            .where(LetterboxdEntry.resolved_at.is_(None))
            .order_by(LetterboxdEntry.watched_date.desc(), LetterboxdEntry.created_at.desc())
        )
        return list(self._session.scalars(statement))

    def film_ids_by_slug(self, slug: str) -> list[uuid.UUID]:
        """Films whose ``letterboxd_url`` points at ``slug`` (FR-LBX-04 rule 1)."""
        # The LIKE narrows the scan; ``film_slug`` then rejects near misses
        # such as ``/film/heat-2/`` for ``heat``.
        statement = select(Film.id, Film.letterboxd_url).where(
            Film.letterboxd_url.contains(f"/film/{slug}", autoescape=True)
        )
        return [
            film_id
            for film_id, url in self._session.execute(statement)
            if url is not None and film_slug(url) == slug
        ]

    def film_ids_by_title_year(self, title: str, year: int) -> list[uuid.UUID]:
        """Films with any title equal to ``title`` (case-insensitive, trimmed) and that year (FR-LBX-04 rule 2)."""
        statement = (
            select(Title.film_id)
            .distinct()
            .join(Film, Film.id == Title.film_id)
            .where(
                func.lower(func.trim(Title.value)) == title.strip().lower(),
                Film.release_year == year,
            )
        )
        return list(self._session.scalars(statement))

    def has_watch_on(self, film_id: uuid.UUID, watch_date: date) -> bool:
        statement = select(RatingEntry.id).where(
            RatingEntry.film_id == film_id, RatingEntry.watch_date == watch_date
        )
        return self._session.scalar(statement.limit(1)) is not None

    def primary_titles(self, film_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not film_ids:
            return {}
        statement = select(Title.film_id, Title.value).where(
            and_(Title.film_id.in_(film_ids), Title.is_primary)
        )
        return {film_id: value for film_id, value in self._session.execute(statement)}  # noqa: C416

    def commit(self) -> None:
        self._session.commit()
