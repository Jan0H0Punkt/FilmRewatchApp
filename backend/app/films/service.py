"""Business-logic layer for the films module (DESIGN §5.1, M1 PR4/PR5/PR6/PR7).

The "log a watched film" flow (FR-LIB-01..05): create a film **together with**
its mandatory first rating, tags, and genres in one atomic unit of work
(FR-LIB-03), duplicate detection over the derived ``natural_key``
(FR-LIB-04/05), and the full §7.3 detail projection with the average computed
on every read (FR-RAT-09/10, NFR-INT-01). PR5 adds the edit flow
(FR-LIB-06..09): every user-editable field, natural-key recomputation, and the
same duplicate block applied to edits. PR6 adds the delete flow
(FR-LIB-10..12): the film and everything cascading from it, plus the
now-orphaned tags/genres, removed atomically. PR7 adds the standalone rating
lifecycle's film-side half (FR-RAT-01..08): adding a rating to an existing
film, and the last-rating-deletes-the-film invariant, reusing PR6's delete
flow verbatim for the cascade + orphan cleanup.

Layering (§5.1): this service depends on the films repository *interface* and
reaches the other modules **service-to-service** — tags/genres via their
``get_or_create``/``assign``/``unassign``/``delete_orphans`` APIs
(FR-TAG-01..04), ratings via ``add_entry``/``get_or_raise``/``count_for_film``/
``delete`` — all sharing the request's session, so one ``commit()`` seals the
whole create (or edit, delete, or rating operation) and any failure rolls
everything back (nothing here commits partially). The standalone rating
endpoints are owned by this service, not ``RatingService``, precisely because
the last-rating case must call back into :meth:`FilmService.delete` — the
reverse dependency direction would be circular (this service already depends
on ``RatingService`` for the create flow's first rating).

Duplicate detection is the pre-check against the derived key; the §5.2 unique
constraint on ``films.natural_key`` remains the database backstop should two
creates/edits ever genuinely race (single-user deployment, §3.6 — a race
surfaces as an ``INTERNAL_ERROR`` rather than a partial write).
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
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
    FilmUpdate,
    TitleRead,
)
from app.genres.models import Genre
from app.ratings.models import RatingEntry
from app.ratings.schemas import RatingDeletionResult, RatingEntryRead
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

    def assign(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None: ...

    def unassign(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None: ...

    def delete_orphans(self) -> int: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Genre]: ...


class RatingHistoryProtocol(Protocol):
    """What the film flow needs of the rating service (service-to-service)."""

    def add_entry(self, film_id: uuid.UUID, value: Decimal, watch_date: date) -> RatingEntry: ...

    def get_or_raise(self, rating_id: uuid.UUID) -> RatingEntry: ...

    def count_for_film(self, film_id: uuid.UUID) -> int: ...

    def delete(self, entry: RatingEntry) -> None: ...

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

    def update(self, film_id: uuid.UUID, data: FilmUpdate) -> FilmDetailRead:
        """Edit a film's user-editable fields (FR-LIB-06..09).

        Every field is optional; a field absent from the request — and, for
        every field except ``poster_image``, an explicit ``null`` too — is
        left unchanged (the schema docstring). ``updated_at`` is bumped only
        when the request actually names at least one field; a body with none
        (``{}``) is a pure no-op that leaves ``updated_at`` untouched.

        All validation, including the duplicate check, runs **before** any
        mutation: a colliding edit raises :class:`DuplicateFilmError` while
        the film is still byte-for-byte as stored (FR-LIB-09) — nothing here
        commits partially, mirroring :meth:`create`.
        """
        film = self._repository.find_by_id(film_id)
        if film is None:
            raise FilmNotFoundError(film_id)

        current_titles = self._repository.list_titles(film_id)
        current_primary = next(title for title in current_titles if title.is_primary)
        effective_primary_value = (
            next(title.value for title in data.titles if title.is_primary)
            if data.titles is not None
            else current_primary.value
        )
        effective_release_year = (
            data.release_year if data.release_year is not None else film.release_year
        )
        effective_director = data.director if data.director is not None else film.director
        new_natural_key = derive_natural_key(
            effective_primary_value, effective_release_year, effective_director
        )

        natural_key_changed = new_natural_key != film.natural_key
        if natural_key_changed:
            collision = self._repository.find_by_natural_key(new_natural_key)
            if collision is not None and collision.id != film.id:
                raise DuplicateFilmError(self._summary_of(collision))
            film.natural_key = new_natural_key

        # Everything below only runs once the duplicate check has passed —
        # the film is guaranteed to end up either fully edited or untouched.
        if data.titles is not None:
            self._repository.delete_titles(film.id)
            for title in data.titles:
                self._repository.add_title(
                    Title(
                        film_id=film.id,
                        value=title.value,
                        is_primary=title.is_primary,
                        is_original=title.is_original,
                    )
                )
        if data.release_year is not None:
            film.release_year = data.release_year
        if data.director is not None:
            film.director = data.director
        if "poster_image" in data.model_fields_set:
            # The one field whose stored value is itself nullable: an explicit
            # null here means "remove" (FR-LIB-15), not "unchanged".
            film.poster_image = data.poster_image
        if data.is_favorite is not None:
            film.is_favorite = data.is_favorite
        if data.delay_days is not None:
            film.delay_days = data.delay_days
        if data.tags is not None:
            self._reassign_tags(film.id, data.tags)
        if data.genre is not None:
            self._reassign_genres(film.id, data.genre)

        if data.model_fields_set:
            film.updated_at = datetime.now(UTC)
        self._repository.commit()
        return self.get_detail(film.id)

    def delete(self, film_id: uuid.UUID) -> None:
        """Delete a film and everything that depends on it (FR-LIB-10..12).

        The film row's removal cascades to its titles, rating entries, and
        tag/genre links at the database level (PR1's ``ON DELETE CASCADE``
        foreign keys); this method then sweeps for tags/genres the deletion
        left on no films (FR-LIB-12, FR-TAG-04). Both steps share the film
        service's one unit of work, sealed by a single commit (NFR-INT-02) —
        a failure anywhere leaves the film, and everything cascading from it,
        exactly as it was.
        """
        film = self._repository.find_by_id(film_id)
        if film is None:
            raise FilmNotFoundError(film_id)
        self._repository.delete_film(film)
        self._tags.delete_orphans()
        self._genres.delete_orphans()
        self._repository.commit()

    def add_rating(self, film_id: uuid.UUID, value: Decimal, watch_date: date) -> RatingEntryRead:
        """Record a new rating event for an existing film (FR-RAT-01..04).

        Unknown film id → :class:`FilmNotFoundError`. A future ``watch_date``
        raises :class:`~app.ratings.service.FutureWatchDateError` from
        :meth:`RatingHistoryProtocol.add_entry` (its own stable code, not
        ``VALIDATION_ERROR``). The average the next detail read computes
        reflects the new entry automatically — it is never stored
        (FR-RAT-10, NFR-INT-01).
        """
        film = self._repository.find_by_id(film_id)
        if film is None:
            raise FilmNotFoundError(film_id)
        entry = self._ratings.add_entry(film_id, value, watch_date)
        self._repository.commit()
        return RatingEntryRead.model_validate(entry)

    def delete_rating(self, rating_id: uuid.UUID) -> RatingDeletionResult:
        """Delete one rating entry, applying the last-rating rule (FR-RAT-07).

        Unknown rating id → ``NOT_FOUND``. If the entry is the film's *last*
        remaining rating, the whole film is deleted via :meth:`delete` — the
        same atomic cascade + orphan cleanup PR6 built — rather than deleting
        the rating row directly (the ``ON DELETE CASCADE`` FK removes it as
        part of that one commit). Otherwise only the rating entry is removed.
        The response tells the two outcomes apart (``film_deleted``) so the M3
        UI knows whether to stay on the film or navigate away from it.
        """
        entry = self._ratings.get_or_raise(rating_id)
        film_id = entry.film_id
        if self._ratings.count_for_film(film_id) <= 1:
            self.delete(film_id)
            return RatingDeletionResult(rating_id=rating_id, film_id=film_id, film_deleted=True)
        self._ratings.delete(entry)
        self._repository.commit()
        return RatingDeletionResult(rating_id=rating_id, film_id=film_id, film_deleted=False)

    def _reassign_tags(self, film_id: uuid.UUID, names: Sequence[str]) -> None:
        """Replace a film's tags with ``names`` (FR-TAG-03/04), orphans reaped."""
        desired = _deduplicated(names)
        desired_keys = {name.strip().lower() for name in desired}
        for tag in self._tags.list_for_film(film_id):
            if tag.name.strip().lower() not in desired_keys:
                self._tags.unassign(film_id, tag.id)
        for name in desired:
            tag = self._tags.get_or_create(name)
            self._tags.assign(film_id, tag.id)
        self._tags.delete_orphans()

    def _reassign_genres(self, film_id: uuid.UUID, names: Sequence[str]) -> None:
        """Replace a film's genres with ``names`` (FR-TAG-03/04 analogue)."""
        desired = _deduplicated(names)
        desired_keys = {name.strip().lower() for name in desired}
        for genre in self._genres.list_for_film(film_id):
            if genre.name.strip().lower() not in desired_keys:
                self._genres.unassign(film_id, genre.id)
        for name in desired:
            genre = self._genres.get_or_create(name)
            self._genres.assign(film_id, genre.id)
        self._genres.delete_orphans()

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
