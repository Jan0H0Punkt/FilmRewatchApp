"""Business-logic layer for the directors module (DESIGN §5.1).

Directors are a shared entity like tags and genres (REQ §4.1), so this mirrors
``app/genres/service.py``: the rules live behind a repository *interface* (the
:class:`DirectorRepositoryProtocol`), keeping the service unit-testable against
a fake (§9) and free of SQL/ORM specifics and HTTP.

Rules enforced here (authoritatively server-side, NFR-INT-03):

- A director name is meaningful text: surrounding whitespace is trimmed, and the
  trimmed name must be 1-255 characters (REQ §4.1) — otherwise ``"Michael Mann"``
  and ``" Michael Mann "`` would coexist as distinct rows under the
  case-insensitive-only unique index (§5.2).
- Creation is always implicit get-or-create (FR-TAG-01/02 analogues): the film
  flows call :meth:`DirectorService.get_or_create` per payload name; there is no
  standalone create.
- Orphan cleanup (FR-TAG-04 analogue) is a service API for the film flows, never
  a user-facing route.

No autocomplete route exists yet (tags and genres have one): nothing in M1 asks
to look directors up by prefix. The repository already supports the lookup the
day a requirement does.
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from fastapi import status

from app.core.errors import AppError
from app.directors.models import Director

_NAME_MAX_LENGTH = 255


class InvalidDirectorNameError(AppError):
    """A director name that violates REQ §4.1 (empty or over 255 chars after trim)."""

    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = (
        f"Director name must be 1-{_NAME_MAX_LENGTH} characters (ignoring surrounding whitespace)."
    )


class DirectorRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1).

    Satisfied structurally by
    :class:`~app.directors.repository.DirectorRepository` and by the in-memory
    fakes the service unit tests inject (§9).
    """

    def get_or_create(self, name: str) -> Director: ...

    def delete_orphans(self) -> int: ...

    def link_film(self, film_id: uuid.UUID, director_id: uuid.UUID, position: int) -> None: ...

    def unlink_all(self, film_id: uuid.UUID) -> None: ...

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Director]: ...


class DirectorService:
    """Director business rules over an injected repository interface."""

    def __init__(self, repository: DirectorRepositoryProtocol) -> None:
        self._repository = repository

    def get_or_create(self, name: str) -> Director:
        """Validate ``name`` and return its director row, creating it if new.

        Case-insensitive dedupe and race safety are the repository's contract;
        this layer owns the name rules (REQ §4.1).
        """
        trimmed = name.strip()
        if not 1 <= len(trimmed) <= _NAME_MAX_LENGTH:
            raise InvalidDirectorNameError()
        return self._repository.get_or_create(trimmed)

    def delete_orphans(self) -> int:
        """Delete directors left on no films (FR-TAG-04 analogue); returns the count."""
        return self._repository.delete_orphans()

    def assign(self, film_id: uuid.UUID, director_id: uuid.UUID, position: int) -> None:
        """Credit a director on a film at ``position``.

        Called service-to-service by the film flows inside their atomic unit of
        work; there is no standalone assignment route. Unlike the label
        services' ``assign``, this is **not** idempotent — the caller replaces
        the whole credit list via :meth:`unassign_all` first (see
        :meth:`~app.directors.repository.DirectorRepository.link_film`).
        """
        self._repository.link_film(film_id, director_id, position)

    def unassign_all(self, film_id: uuid.UUID) -> None:
        """Drop a film's whole credit list, ahead of re-crediting it.

        The ordered analogue of the label services' per-label ``unassign``:
        positions are only meaningful for a complete list, so the film flows
        replace it wholesale rather than diffing it. The caller runs
        :meth:`delete_orphans` afterwards to reap directors the replacement left
        on no films.
        """
        self._repository.unlink_all(film_id)

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Director]:
        """The film's directors for the §7.3 detail projection, in credited order."""
        return self._repository.list_for_film(film_id)
