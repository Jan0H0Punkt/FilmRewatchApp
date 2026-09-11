"""Business-logic layer for the tags module (DESIGN §5.1, M1 PR3).

The tags-specific rules live here, behind a repository *interface* (the
:class:`TagRepositoryProtocol`), so the service is unit-testable against a fake
(§9) and never touches SQL/ORM specifics or HTTP.

Rules enforced here (authoritatively server-side, NFR-INT-03):

- A tag name is meaningful text: surrounding whitespace is trimmed, and the
  trimmed name must be 1-50 characters (REQ §4.3) — otherwise ``"Drama"`` and
  ``" Drama "`` would coexist as distinct rows under the case-insensitive-only
  unique index (§5.2).
- Creation is always implicit get-or-create (FR-TAG-01/02): the film flows
  (M1 PR4+) call :meth:`TagService.get_or_create` per payload label; there is no
  standalone create.
- Orphan cleanup (FR-TAG-04) is a service API for the film flows (PR5/PR6/PR7),
  never a user-facing route.
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from fastapi import status

from app.core.errors import AppError
from app.tags.models import Tag

_NAME_MAX_LENGTH = 50


class InvalidTagNameError(AppError):
    """A tag name that violates REQ §4.3 (empty or over 50 chars after trim)."""

    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = f"Tag name must be 1-{_NAME_MAX_LENGTH} characters (ignoring surrounding whitespace)."


class TagRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1).

    Satisfied structurally by :class:`~app.tags.repository.TagRepository` and by
    the in-memory fakes the service unit tests inject (§9).
    """

    def get_or_create(self, name: str) -> Tag: ...

    def list_by_prefix(self, prefix: str | None = None) -> Sequence[Tag]: ...

    def delete_orphans(self) -> int: ...

    def link_film(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None: ...

    def unlink_film(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Tag]: ...


class TagService:
    """Tag business rules over an injected repository interface."""

    def __init__(self, repository: TagRepositoryProtocol) -> None:
        self._repository = repository

    def get_or_create(self, name: str) -> Tag:
        """Validate ``name`` and return its tag row, creating it if new.

        Case-insensitive dedupe (FR-TAG-02) and race safety are the
        repository's contract; this layer owns the name rules (REQ §4.3).
        """
        trimmed = name.strip()
        if not 1 <= len(trimmed) <= _NAME_MAX_LENGTH:
            raise InvalidTagNameError()
        return self._repository.get_or_create(trimmed)

    def list_by_prefix(self, prefix: str | None = None) -> Sequence[Tag]:
        """List tags for the autocomplete lookup (FR-TAG-06 backend half)."""
        return self._repository.list_by_prefix(prefix)

    def delete_orphans(self) -> int:
        """Delete tags left on no films (FR-TAG-04); returns how many died."""
        return self._repository.delete_orphans()

    def assign(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        """Assign a tag to a film (FR-TAG-03) — idempotent, per the repository.

        Called service-to-service by the film flows (M1 PR4/PR5) inside their
        atomic unit of work; there is no standalone assignment route.
        """
        self._repository.link_film(film_id, tag_id)

    def unassign(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        """Remove a tag from a film (FR-TAG-04) — idempotent, per the repository.

        Called service-to-service by the film flows (M1 PR5+) inside their
        atomic unit of work; the caller runs :meth:`delete_orphans` afterwards
        to reap labels the removal left on no films.
        """
        self._repository.unlink_film(film_id, tag_id)

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Tag]:
        """The film's tags for the §7.3 detail projection, alphabetically."""
        return self._repository.list_for_film(film_id)
