"""The films module's domain error types (DESIGN §5.1, NFR-MAINT-03).

Each subclass fixes the ``code``/``status_code``/``message`` triple the
``core.errors`` envelope renders, so a route never has to shape an error.
"""

import uuid

from fastapi import status

from app.core.errors import AppError
from app.films.schemas import FilmSummary


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
