"""Data-access layer for the stats module (DESIGN §5.1).

Three reads, no rules: every rating entry joined with its film's primary
title and metadata, every film's genres, and every film's tags. Genres and
tags each come from their own query because joining them in would repeat
each entry once per association.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.genres.models import FilmGenre, Genre
from app.ratings.models import RatingEntry
from app.ratings.service import EARLIER_WATCH_DATE
from app.stats.algorithm import Watch
from app.tags.models import FilmTag, Tag


class StatsRepository:
    """SQLAlchemy-backed stats data access (one instance per session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def watches(self) -> list[Watch]:
        """Every rating entry as a :class:`Watch`; ``EARLIER_WATCH_DATE`` becomes ``None``."""
        genres: defaultdict[UUID, list[str]] = defaultdict(list)
        genre_rows = self._session.execute(
            select(FilmGenre.film_id, Genre.name)
            .join(Genre, Genre.id == FilmGenre.genre_id)
            .order_by(FilmGenre.position)
        )
        for film_id, name in genre_rows:
            genres[film_id].append(name)

        tags: defaultdict[UUID, list[str]] = defaultdict(list)
        tag_rows = self._session.execute(
            select(FilmTag.film_id, Tag.name).join(Tag, Tag.id == FilmTag.tag_id).order_by(Tag.name)
        )
        for film_id, name in tag_rows:
            tags[film_id].append(name)

        statement = (
            select(
                RatingEntry.film_id,
                RatingEntry.watch_date,
                RatingEntry.value,
                Title.value.label("title"),
                Film.release_year,
                Film.director,
                Film.runtime_minutes,
            )
            .join(Film, Film.id == RatingEntry.film_id)
            .join(Title, and_(Title.film_id == Film.id, Title.is_primary))
        )
        return [
            Watch(
                film_id=row.film_id,
                title=row.title,
                release_year=row.release_year,
                director=row.director,
                runtime_minutes=row.runtime_minutes,
                genres=tuple(genres[row.film_id]),
                tags=tuple(tags[row.film_id]),
                watch_date=None if row.watch_date == EARLIER_WATCH_DATE else row.watch_date,
                value=row.value,
            )
            for row in self._session.execute(statement)
        ]
