"""The interfaces :class:`~app.films.service.FilmService` depends on (§5.1).

One protocol per collaborator: the films repository, plus the tag, genre, and
rating services reached **service-to-service**. Keeping them structural is what
lets the unit tests inject in-memory fakes (§9) without touching the database.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.films.models import Film, Title
from app.genres.models import Genre
from app.ratings.models import RatingEntry
from app.tags.models import Tag


class FilmRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1).

    Satisfied structurally by :class:`~app.films.repository.FilmRepository` and
    by the in-memory fakes the service unit tests inject (§9). ``commit`` seals
    the unit of work — transaction control belongs to this service, mechanics
    to the repository.
    """

    def add_film(self, film: Film) -> None: ...

    def add_title(self, title: Title) -> None: ...

    def find_by_id(self, film_id: uuid.UUID) -> Film | None: ...

    def find_by_natural_key(self, natural_key: str) -> Film | None: ...

    def list_films(self) -> Sequence[Film]: ...

    def list_titles(self, film_id: uuid.UUID) -> Sequence[Title]: ...

    def delete_titles(self, film_id: uuid.UUID) -> None: ...

    def delete_film(self, film: Film) -> None: ...

    def commit(self) -> None: ...


class TagAssignmentProtocol(Protocol):
    """What the film flow needs of the tag service (service-to-service, §5.1)."""

    def get_or_create(self, name: str) -> Tag: ...

    def assign(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None: ...

    def unassign(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None: ...

    def delete_orphans(self) -> int: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Tag]: ...


class GenreAssignmentProtocol(Protocol):
    """What the film flow needs of the genre service (service-to-service)."""

    def get_or_create(self, name: str) -> Genre: ...

    def assign(self, film_id: uuid.UUID, genre_id: uuid.UUID, position: int) -> None: ...

    def unassign(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None: ...

    def delete_orphans(self) -> int: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Genre]: ...


class RatingHistoryProtocol(Protocol):
    """What the film flow needs of the rating service (service-to-service)."""

    def add_entry(
        self, film_id: uuid.UUID, value: Decimal | None, watch_date: date
    ) -> RatingEntry: ...

    def get_or_raise(self, rating_id: uuid.UUID) -> RatingEntry: ...

    def count_for_film(self, film_id: uuid.UUID) -> int: ...

    def delete(self, entry: RatingEntry) -> None: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]: ...
