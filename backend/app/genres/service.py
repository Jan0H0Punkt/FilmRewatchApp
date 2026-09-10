"""Business-logic layer for the genres module (DESIGN §5.1, M1 PR3).

Genres behave identically to tags (REQ §4.4), so this mirrors
``app/tags/service.py``: the rules live behind a repository *interface* (the
:class:`GenreRepositoryProtocol`), keeping the service unit-testable against a
fake (§9) and free of SQL/ORM specifics and HTTP.

Rules enforced here (authoritatively server-side, NFR-INT-03):

- A genre name is meaningful text: surrounding whitespace is trimmed, and the
  trimmed name must be 1-100 characters (REQ §4.4) — otherwise ``"Drama"`` and
  ``" Drama "`` would coexist as distinct rows under the case-insensitive-only
  unique index (§5.2).
- Creation is always implicit get-or-create (FR-TAG-01/02 analogues): the film
  flows (M1 PR4+) call :meth:`GenreService.get_or_create` per payload label;
  there is no standalone create.
- Orphan cleanup (FR-TAG-04 analogue) is a service API for the film flows
  (PR5/PR6/PR7), never a user-facing route.
"""

from collections.abc import Sequence
from typing import Protocol

from fastapi import status

from app.core.errors import AppError
from app.genres.models import Genre

_NAME_MAX_LENGTH = 100


class InvalidGenreNameError(AppError):
    """A genre name that violates REQ §4.4 (empty or over 100 chars after trim)."""

    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = (
        f"Genre name must be 1-{_NAME_MAX_LENGTH} characters (ignoring surrounding whitespace)."
    )


class GenreRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1).

    Satisfied structurally by :class:`~app.genres.repository.GenreRepository`
    and by the in-memory fakes the service unit tests inject (§9).
    """

    def get_or_create(self, name: str) -> Genre: ...

    def list_by_prefix(self, prefix: str | None = None) -> Sequence[Genre]: ...

    def delete_orphans(self) -> int: ...


class GenreService:
    """Genre business rules over an injected repository interface."""

    def __init__(self, repository: GenreRepositoryProtocol) -> None:
        self._repository = repository

    def get_or_create(self, name: str) -> Genre:
        """Validate ``name`` and return its genre row, creating it if new.

        Case-insensitive dedupe (FR-TAG-02 analogue) and race safety are the
        repository's contract; this layer owns the name rules (REQ §4.4).
        """
        trimmed = name.strip()
        if not 1 <= len(trimmed) <= _NAME_MAX_LENGTH:
            raise InvalidGenreNameError()
        return self._repository.get_or_create(trimmed)

    def list_by_prefix(self, prefix: str | None = None) -> Sequence[Genre]:
        """List genres for the autocomplete lookup (FR-TAG-06 analogue)."""
        return self._repository.list_by_prefix(prefix)

    def delete_orphans(self) -> int:
        """Delete genres left on no films (FR-TAG-04 analogue); returns the count."""
        return self._repository.delete_orphans()
