"""Business logic for the Letterboxd sync (REQ §5.7).

:func:`run_sync` is the sync itself — module-level so the background loop can
call it without the request-scoped ``FilmService`` it never needs (FR-LBX-05).
"""

import threading
import uuid
from collections.abc import Callable, Collection, Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.core.db import utc_now
from app.films.schemas import FilmDetailRead, FilmUpdate
from app.letterboxd.errors import EntryNotFoundError, EntryResolvedError
from app.letterboxd.feed import FeedEntry, film_slug
from app.letterboxd.models import LetterboxdEntry
from app.letterboxd.schemas import LetterboxdEntryRead, SuggestedFilmRead
from app.ratings.schemas import RatingEntryRead

# Keeps the scheduled and a manual sync from interleaving; the ``guid`` unique
# constraint is the backstop. ponytail: one process only — a second backend
# worker would need a database advisory lock instead.
_SYNC_LOCK = threading.Lock()


class LetterboxdRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1)."""

    def is_known_guid(self, guid: str) -> bool: ...

    def add(self, entry: LetterboxdEntry) -> None: ...

    def get(self, entry_id: uuid.UUID) -> LetterboxdEntry | None: ...

    def list_open(self) -> list[LetterboxdEntry]: ...

    def film_ids_by_slug(self, slug: str) -> list[uuid.UUID]: ...

    def film_ids_by_title_year(self, title: str, year: int) -> list[uuid.UUID]: ...

    def has_watch_on(self, film_id: uuid.UUID, watch_date: date) -> bool: ...

    def primary_titles(self, film_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]: ...

    def commit(self) -> None: ...


def match_film(
    repository: LetterboxdRepositoryProtocol, slug: str | None, title: str, year: int
) -> uuid.UUID | None:
    """The one film an entry belongs to, or ``None`` for zero or several (FR-LBX-04)."""
    if slug is not None:
        by_slug = repository.film_ids_by_slug(slug)
        if len(by_slug) == 1:
            return by_slug[0]
    by_title = repository.film_ids_by_title_year(title, year)
    return by_title[0] if len(by_title) == 1 else None


def run_sync(
    repository: LetterboxdRepositoryProtocol, entries: Sequence[FeedEntry], today: date
) -> int:
    """Queue the feed's new entries for review; returns how many were queued (FR-LBX-02..05)."""
    with _SYNC_LOCK:
        queued = 0
        for entry in entries:
            if repository.is_known_guid(entry.guid):
                break
            film_id = match_film(repository, entry.film_slug, entry.film_title, entry.film_year)
            if film_id is not None and repository.has_watch_on(film_id, entry.watched_date):
                break
            if entry.watched_date > today:
                continue  # FR-LBX-03: the next sync picks it up
            repository.add(
                LetterboxdEntry(
                    guid=entry.guid,
                    film_title=entry.film_title,
                    film_year=entry.film_year,
                    film_url=entry.film_url,
                    watched_date=entry.watched_date,
                    rating=entry.rating,
                    rewatch=entry.rewatch,
                    suggested_film_id=film_id,
                )
            )
            queued += 1
        repository.commit()
        return queued


class FilmWriter(Protocol):
    """The ``FilmService`` calls the review actions need (service-to-service, §5.1)."""

    def add_rating(
        self, film_id: uuid.UUID, value: Decimal | None, watch_date: date
    ) -> RatingEntryRead: ...

    def get_detail(self, film_id: uuid.UUID) -> FilmDetailRead: ...

    def update(self, film_id: uuid.UUID, data: FilmUpdate) -> FilmDetailRead: ...


class LetterboxdService:
    """The review list's reads and actions (FR-LBX-05..07), plus the manual sync."""

    def __init__(
        self,
        repository: LetterboxdRepositoryProtocol,
        films: FilmWriter,
        fetch: Callable[[], list[FeedEntry]],
        today: Callable[[], date] = date.today,
    ) -> None:
        self._repository = repository
        self._films = films
        self._fetch = fetch
        self._today = today

    def sync(self) -> int:
        """Fetch the feed and queue its new entries; returns how many were queued."""
        return run_sync(self._repository, self._fetch(), self._today())

    def list_open(self) -> list[LetterboxdEntryRead]:
        """Open entries, newest watch first, after auto-resolving the ones now in the app (FR-LBX-07).

        Resolving one entry of an unknown film (e.g. by creating it) leaves
        sibling entries of that same film still open, so each one's displayed
        suggestion is the freshly recomputed match, not the stale one from
        sync time — otherwise a sibling would still say "no match" with no
        way to approve it, inviting a duplicate film.
        """
        still_open: list[tuple[LetterboxdEntry, uuid.UUID | None]] = []
        resolved_any = False
        for entry in self._repository.list_open():
            film_id = match_film(
                self._repository, film_slug(entry.film_url), entry.film_title, entry.film_year
            )
            if film_id is not None and self._repository.has_watch_on(film_id, entry.watched_date):
                entry.resolved_at = utc_now()
                resolved_any = True
            else:
                still_open.append((entry, film_id))
        if resolved_any:
            self._repository.commit()

        suggested_ids = {
            suggested_id
            for entry, film_id in still_open
            if (suggested_id := film_id if film_id is not None else entry.suggested_film_id)
            is not None
        }
        titles = self._repository.primary_titles(suggested_ids)
        return [
            LetterboxdEntryRead(
                id=entry.id,
                film_title=entry.film_title,
                film_year=entry.film_year,
                film_url=entry.film_url,
                watched_date=entry.watched_date,
                rating=float(entry.rating) if entry.rating is not None else None,
                rewatch=entry.rewatch,
                suggested_film=(
                    SuggestedFilmRead(id=suggested_id, title=titles[suggested_id])
                    if (
                        suggested_id := (
                            film_id if film_id is not None else entry.suggested_film_id
                        )
                    )
                    is not None
                    and suggested_id in titles
                    else None
                ),
            )
            for entry, film_id in still_open
        ]

    def assign(self, entry_id: uuid.UUID, film_id: uuid.UUID) -> None:
        """Add the entry's watch to ``film_id`` and resolve it (FR-LBX-06).

        An unknown film raises ``FilmNotFoundError`` from ``add_rating`` before
        anything is committed, so the entry stays open.
        """
        entry = self._open_entry(entry_id)
        entry.resolved_at = utc_now()
        self._films.add_rating(film_id, entry.rating, entry.watched_date)
        if self._films.get_detail(film_id).letterboxd_url is None:
            self._films.update(film_id, FilmUpdate(letterboxd_url=entry.film_url))
        self._repository.commit()

    def dismiss(self, entry_id: uuid.UUID) -> None:
        """Resolve the entry without adding anything (FR-LBX-06)."""
        self._open_entry(entry_id).resolved_at = utc_now()
        self._repository.commit()

    def _open_entry(self, entry_id: uuid.UUID) -> LetterboxdEntry:
        entry = self._repository.get(entry_id)
        if entry is None:
            raise EntryNotFoundError(entry_id)
        if entry.resolved_at is not None:
            raise EntryResolvedError(entry_id)
        return entry
