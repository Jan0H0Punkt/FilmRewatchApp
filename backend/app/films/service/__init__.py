"""Business-logic layer for the films module (DESIGN §5.1, M1 PR4/PR5/PR6/PR7).

The "log a watched film" flow (FR-LIB-01..05): create a film **together with**
its mandatory first rating, tags, and genres in one atomic unit of work
(FR-LIB-03), duplicate detection over the derived ``natural_key``
(FR-LIB-04/05), and the full §7.3 detail projection carrying the full
``rating_history`` the client derives its average from (FR-RAT-09/10,
NFR-INT-01). PR5 adds the edit flow
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

A folder rather than one file (the ~200-line escape hatch in
``backend/CLAUDE.md``): ``orchestration.py`` holds the flows, ``protocols.py``
the collaborator interfaces, ``errors.py`` the domain error types, and
``normalisation.py`` the text-normalising helpers they share. This module
re-exports the public API, so ``from app.films.service import FilmService``
keeps working.
"""

from app.films.service.errors import DuplicateFilmError, FilmIdCollisionError, FilmNotFoundError
from app.films.service.normalisation import derive_natural_key
from app.films.service.orchestration import FilmService
from app.films.service.protocols import (
    FilmRepositoryProtocol,
    GenreAssignmentProtocol,
    PosterPaletteFetcher,
    RatingHistoryProtocol,
    TagAssignmentProtocol,
)

__all__ = [
    "DuplicateFilmError",
    "FilmIdCollisionError",
    "FilmNotFoundError",
    "FilmRepositoryProtocol",
    "FilmService",
    "GenreAssignmentProtocol",
    "PosterPaletteFetcher",
    "RatingHistoryProtocol",
    "TagAssignmentProtocol",
    "derive_natural_key",
]
