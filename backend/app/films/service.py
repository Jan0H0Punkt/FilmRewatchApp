"""Business-logic layer for the films module (DESIGN §5.1, M1 PR4).

The "log a watched film" flow (FR-LIB-01..05): create a film **together with**
its mandatory first rating, tags, and genres in one atomic unit of work
(FR-LIB-03), duplicate detection over the derived ``natural_key``
(FR-LIB-04/05), and the full §7.3 detail projection with the average computed
on every read (FR-RAT-09/10, NFR-INT-01).

Layering (§5.1): this service depends on the films repository *interface* and
reaches the other modules **service-to-service** — tags/genres via their
``get_or_create``/``assign`` APIs (FR-TAG-01..03), ratings via ``add_entry`` —
all sharing the request's session, so one ``commit()`` seals the whole create
and any failure rolls everything back (nothing here commits partially).

Duplicate detection is the pre-check against the derived key; the §5.2 unique
constraint on ``films.natural_key`` remains the database backstop should two
creates ever genuinely race (single-user deployment, §3.6 — a race surfaces as
an ``INTERNAL_ERROR`` rather than a partial write).
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from fastapi import status

from app.core.errors import AppError
from app.films.models import Film, Title
from app.films.schemas import (
    DuplicateCheckResult,
    FilmCreate,
    FilmDetailRead,
    FilmSummary,
    TitleRead,
)
from app.genres.models import Genre
from app.ratings.models import RatingEntry
from app.ratings.schemas import RatingEntryRead
from app.tags.models import Tag


def derive_natural_key(primary_title: str, release_year: int, director: str) -> str:
    """The FR-LIB-04 derivation — duplicate detection's whole identity notion.

    ``lowercase(trim(primary_title))|release_year|lowercase(trim(director))``:
    case- and surrounding-whitespace-insensitive on the text parts (REQ §4.1
    note). Derived and consumed server-side only; never in a schema.
    """
    return f"{primary_title.strip().lower()}|{release_year}|{director.strip().lower()}"


class FilmNotFoundError(AppError):
    """No film with the requested id (rendered as the ``NOT_FOUND`` envelope)."""

    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND
    message = "Film not found."

    def __init__(self, film_id: uuid.UUID) -> None:
        super().__init__(f"Film {film_id} not found.")


class FilmIdCollisionError(AppError):
    """A client-minted id that already exists (§5.5 scoping note).

    In M1 this is plainly a validation error; the replay-returns-existing
    semantics arrive with the M6 sync queue.
    """

    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = "A film with this id already exists."

    def __init__(self, film_id: uuid.UUID) -> None:
        super().__init__(f"A film with id {film_id} already exists.")


class DuplicateFilmError(AppError):
    """The FR-LIB-05/09 duplicate block, identifying the existing film.

    The envelope carries only ``code``/``message`` (NFR-MAINT-03), so the
    message names the collision — primary title, year, director, and id — and
    the structured identification lives on :attr:`existing` (consumed by the
    duplicate-check probe and, in M7, the merge hook). The user cannot
    override the block.
    """

    code = "DUPLICATE_FILM"
    status_code = status.HTTP_409_CONFLICT
    message = "A film with the same primary title, release year, and director already exists."

    def __init__(self, existing: FilmSummary) -> None:
        self.existing = existing
        super().__init__(
            f'Duplicate of existing film "{existing.primary_title}" '
            f"({existing.release_year}, {existing.director}) — id {existing.id}."
        )


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

    def list_titles(self, film_id: uuid.UUID) -> Sequence[Title]: ...

    def commit(self) -> None: ...


class TagAssignmentProtocol(Protocol):
    """What the film flow needs of the tag service (service-to-service, §5.1)."""

    def get_or_create(self, name: str) -> Tag: ...

    def assign(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Tag]: ...


class GenreAssignmentProtocol(Protocol):
    """What the film flow needs of the genre service (service-to-service)."""

    def get_or_create(self, name: str) -> Genre: ...

    def assign(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Genre]: ...


class RatingHistoryProtocol(Protocol):
    """What the film flow needs of the rating service (service-to-service)."""

    def add_entry(self, film_id: uuid.UUID, value: Decimal, watch_date: date) -> RatingEntry: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]: ...


def _deduplicated(names: Sequence[str]) -> list[str]:
    """Payload labels deduplicated the way the store is unique: trimmed,
    case-insensitively, first spelling wins — so ``["Drama", "drama"]`` links
    one row once instead of tripping the join table's primary key."""
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        key = name.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(name)
    return unique


def _average_of(values: Sequence[Decimal]) -> float:
    """Arithmetic mean to one decimal, half-up (FR-RAT-09) — computed on read,
    never stored (NFR-INT-01). The history is never empty (FR-LIB-03)."""
    assert values, "a film always has at least one rating (FR-LIB-03)"
    mean = sum(values, Decimal(0)) / len(values)
    return float(mean.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


class FilmService:
    """Film business rules over the injected repository + peer services."""

    def __init__(
        self,
        repository: FilmRepositoryProtocol,
        tags: TagAssignmentProtocol,
        genres: GenreAssignmentProtocol,
        ratings: RatingHistoryProtocol,
    ) -> None:
        self._repository = repository
        self._tags = tags
        self._genres = genres
        self._ratings = ratings

    def create(self, data: FilmCreate) -> FilmDetailRead:
        """The atomic "log a watched film" flow (FR-LIB-01..05).

        Film + titles + first rating + tag/genre links join one unit of work,
        sealed by a single commit — a failure at any step (e.g. an invalid
        label name) leaves no partial rows. Returns the full §7.3 projection
        of the created film.
        """
        primary = next(title for title in data.titles if title.is_primary)
        natural_key = derive_natural_key(primary.value, data.release_year, data.director)
        existing = self._repository.find_by_natural_key(natural_key)
        if existing is not None:
            raise DuplicateFilmError(self._summary_of(existing))
        if data.id is not None and self._repository.find_by_id(data.id) is not None:
            raise FilmIdCollisionError(data.id)

        film = Film(
            # §5.5 scoping note: client-minted id honoured, server-generated
            # otherwise. is_favorite/delay_days ride the model's system
            # defaults — they are not accepted at create (FR-LIB-02).
            id=data.id if data.id is not None else uuid.uuid4(),
            natural_key=natural_key,
            release_year=data.release_year,
            director=data.director,
            poster_image=data.poster_image,
        )
        self._repository.add_film(film)
        for title in data.titles:
            self._repository.add_title(
                Title(
                    film_id=film.id,
                    value=title.value,
                    is_primary=title.is_primary,
                    is_original=title.is_original,
                )
            )
        self._ratings.add_entry(film.id, data.first_rating.value, data.first_rating.watch_date)
        for name in _deduplicated(data.tags):
            tag = self._tags.get_or_create(name)
            self._tags.assign(film.id, tag.id)
        for name in _deduplicated(data.genre):
            genre = self._genres.get_or_create(name)
            self._genres.assign(film.id, genre.id)
        self._repository.commit()
        return self.get_detail(film.id)

    def get_detail(self, film_id: uuid.UUID) -> FilmDetailRead:
        """The full §7.3 projection — history most recent first (FR-RAT-05/06),
        average computed from it on this read (FR-RAT-09/10, NFR-INT-01)."""
        film = self._repository.find_by_id(film_id)
        if film is None:
            raise FilmNotFoundError(film_id)
        history = self._ratings.list_for_film(film.id)
        return FilmDetailRead(
            id=film.id,
            titles=[
                TitleRead.model_validate(title) for title in self._repository.list_titles(film.id)
            ],
            release_year=film.release_year,
            director=film.director,
            genre=[genre.name for genre in self._genres.list_for_film(film.id)],
            tags=[tag.name for tag in self._tags.list_for_film(film.id)],
            poster_image=film.poster_image,
            is_favorite=film.is_favorite,
            delay_days=film.delay_days,
            rating_history=[RatingEntryRead.model_validate(entry) for entry in history],
            average_rating=_average_of([entry.value for entry in history]),
            created_at=film.created_at,
            updated_at=film.updated_at,
        )

    def check_duplicate(
        self, primary_title: str, release_year: int, director: str
    ) -> DuplicateCheckResult:
        """The FR-LIB-05 background probe: same verdict as the create's block,
        by natural-key parts, with **no** side effects."""
        existing = self._repository.find_by_natural_key(
            derive_natural_key(primary_title, release_year, director)
        )
        if existing is None:
            return DuplicateCheckResult(duplicate=False, film=None)
        return DuplicateCheckResult(duplicate=True, film=self._summary_of(existing))

    def _summary_of(self, film: Film) -> FilmSummary:
        """Enough of a film to name it and open it (FR-LIB-05)."""
        titles = self._repository.list_titles(film.id)
        primary = next(title for title in titles if title.is_primary)
        return FilmSummary(
            id=film.id,
            primary_title=primary.value,
            release_year=film.release_year,
            director=film.director,
        )
