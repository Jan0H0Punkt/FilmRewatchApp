"""The film flows themselves: :class:`FilmService` (DESIGN §5.1).

Create, edit, delete, read, and the standalone rating half — each one a unit of
work this class opens and seals. See the package docstring for why the flows
live together and who they call; the rules they enforce are on the methods.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from app.films.models import Film, Title
from app.films.schemas import (
    DuplicateCheckResult,
    FilmCreate,
    FilmDetailRead,
    FilmSummary,
    FilmUpdate,
    TitleRead,
)
from app.films.service.errors import DuplicateFilmError, FilmIdCollisionError, FilmNotFoundError
from app.films.service.normalisation import deduplicated, derive_natural_key
from app.films.service.protocols import (
    FilmRepositoryProtocol,
    GenreAssignmentProtocol,
    RatingHistoryProtocol,
    TagAssignmentProtocol,
)
from app.ratings.schemas import RatingDeletionResult, RatingEntryRead


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
            runtime_minutes=data.runtime_minutes,
            poster_image=data.poster_image,
            letterboxd_url=data.letterboxd_url,
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
        for name in deduplicated(data.tags):
            tag = self._tags.get_or_create(name)
            self._tags.assign(film.id, tag.id)
        for position, name in enumerate(deduplicated(data.genre)):
            genre = self._genres.get_or_create(name)
            self._genres.assign(film.id, genre.id, position)
        self._repository.commit()
        return self.get_detail(film.id)

    def list_all(self) -> list[FilmDetailRead]:
        """The whole library, primary title alphabetical (the §7.2 result list).

        Each entry is the same §7.3 projection a detail read returns: the list
        needs poster, title, year, director, genre, tags, and the rating
        history the client derives its average from, and reusing one shape
        keeps the client on a single film type.
        """
        # ponytail: one detail projection per film (a handful of queries each)
        # — a single-user library stays small. Fold the per-film lookups into
        # joined/aggregate queries if the list read ever gets slow.
        return [self.get_detail(film.id) for film in self._repository.list_films()]

    def get_detail(self, film_id: uuid.UUID) -> FilmDetailRead:
        """The full §7.3 projection — history most recent first (FR-RAT-05/06),
        from which the client derives the average (FR-RAT-09/10, NFR-INT-01)."""
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
            runtime_minutes=film.runtime_minutes,
            genre=[genre.name for genre in self._genres.list_for_film(film.id)],
            tags=[tag.name for tag in self._tags.list_for_film(film.id)],
            poster_image=film.poster_image,
            letterboxd_url=film.letterboxd_url,
            is_favorite=film.is_favorite,
            delay_days=film.delay_days,
            rating_history=[RatingEntryRead.model_validate(entry) for entry in history],
            created_at=film.created_at,
            updated_at=film.updated_at,
        )

    def update(self, film_id: uuid.UUID, data: FilmUpdate) -> FilmDetailRead:
        """Edit a film's user-editable fields (FR-LIB-06..09).

        Every field is optional; a field absent from the request — and, for
        every field except ``poster_image``/``letterboxd_url``, an explicit
        ``null`` too — is left unchanged (the schema docstring). ``updated_at``
        is bumped only when the request actually names at least one field; a
        body with none (``{}``) is a pure no-op that leaves ``updated_at``
        untouched.

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
        if data.runtime_minutes is not None:
            film.runtime_minutes = data.runtime_minutes
        if "poster_image" in data.model_fields_set:
            # One of the two fields whose stored value is itself nullable: an
            # explicit null here means "remove", not "unchanged" — FR-LIB-15 for
            # the poster, REQ §4.1 for the Letterboxd link.
            film.poster_image = data.poster_image
        if "letterboxd_url" in data.model_fields_set:
            film.letterboxd_url = data.letterboxd_url
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

    def add_rating(
        self, film_id: uuid.UUID, value: Decimal | None, watch_date: date
    ) -> RatingEntryRead:
        """Record a new rating event for an existing film (FR-RAT-01..04).

        A ``value`` of ``None`` logs the watch without scoring it
        (FR-RAT-12). Unknown film id → :class:`FilmNotFoundError`. A future ``watch_date``
        raises :class:`~app.ratings.service.FutureWatchDateError` from
        :meth:`RatingHistoryProtocol.add_entry` (its own stable code, not
        ``VALIDATION_ERROR``). The next detail read's ``rating_history``
        reflects the new entry automatically, so the client's derived
        average does too (FR-RAT-10, NFR-INT-01).
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
        desired = deduplicated(names)
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
        desired = deduplicated(names)
        desired_keys = {name.strip().lower() for name in desired}
        for genre in self._genres.list_for_film(film_id):
            if genre.name.strip().lower() not in desired_keys:
                self._genres.unassign(film_id, genre.id)
        for position, name in enumerate(desired):
            genre = self._genres.get_or_create(name)
            self._genres.assign(film_id, genre.id, position)
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
