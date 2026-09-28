"""The letterboxd module's domain error types (NFR-MAINT-03, REQ §5.7)."""

import uuid

from fastapi import status

from app.core.errors import AppError


class LetterboxdDisabledError(AppError):
    """No ``LETTERBOXD_USERNAME`` is configured, so there is no feed to sync (FR-LBX-01)."""

    code = "LETTERBOXD_DISABLED"
    status_code = status.HTTP_409_CONFLICT
    message = "The Letterboxd sync is off: LETTERBOXD_USERNAME is not set."


class LetterboxdUnavailableError(AppError):
    """The feed could not be fetched or parsed."""

    code = "LETTERBOXD_UNAVAILABLE"
    status_code = status.HTTP_502_BAD_GATEWAY
    message = "The Letterboxd feed could not be read."


class EntryNotFoundError(AppError):
    """No review-list entry with the requested id."""

    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND
    message = "Letterboxd entry not found."

    def __init__(self, entry_id: uuid.UUID) -> None:
        super().__init__(f"Letterboxd entry {entry_id} not found.")


class EntryResolvedError(AppError):
    """The entry was already approved, assigned, dismissed or auto-resolved (FR-LBX-06)."""

    code = "ENTRY_RESOLVED"
    status_code = status.HTTP_409_CONFLICT
    message = "This Letterboxd entry has already been resolved."

    def __init__(self, entry_id: uuid.UUID) -> None:
        super().__init__(f"Letterboxd entry {entry_id} has already been resolved.")
