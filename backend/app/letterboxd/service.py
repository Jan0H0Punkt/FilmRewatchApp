"""Business logic for the Letterboxd sync (REQ §5.7).

:func:`run_sync` is the sync itself — module-level so the background loop can
call it without the request-scoped ``FilmService`` it never needs (FR-LBX-05).
"""

import threading
import uuid
from collections.abc import Collection, Sequence
from datetime import date
from typing import Protocol

from app.letterboxd.feed import FeedEntry
from app.letterboxd.models import LetterboxdEntry

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
