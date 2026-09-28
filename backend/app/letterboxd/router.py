"""Presentation layer for the letterboxd module (REQ §5.7, FR-LBX-01/05..07)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.errors import error_responses
from app.letterboxd.dependencies import get_letterboxd_service
from app.letterboxd.schemas import AssignBody, LetterboxdEntryRead, SyncResult
from app.letterboxd.service import LetterboxdService

router = APIRouter()

Service = Annotated[LetterboxdService, Depends(get_letterboxd_service)]


@router.get(
    "/entries",
    summary="List open Letterboxd entries",
    description=(
        "Open review-list entries, newest watch first. Entries whose watch is "
        "already in the app are resolved first (FR-LBX-07)."
    ),
)
def list_entries(service: Service) -> list[LetterboxdEntryRead]:
    return service.list_open()


@router.post(
    "/entries/{entry_id}/assign",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add an entry's watch to a film",
    description=(
        "Approves the suggestion or assigns another film (FR-LBX-06): adds the "
        "watch with the entry's date and rating and sets the film's Letterboxd "
        "link when it has none."
    ),
    responses=error_responses(
        {
            404: ["NOT_FOUND"],
            409: ["ENTRY_RESOLVED"],
            422: ["VALIDATION_ERROR", "FUTURE_WATCH_DATE"],
        }
    ),
)
def assign_entry(entry_id: UUID, body: AssignBody, service: Service) -> None:
    service.assign(entry_id, body.film_id)


@router.post(
    "/entries/{entry_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dismiss an entry",
    description="Resolves the entry without adding anything (FR-LBX-06).",
    responses=error_responses(
        {422: ["VALIDATION_ERROR"], 404: ["NOT_FOUND"], 409: ["ENTRY_RESOLVED"]}
    ),
)
def dismiss_entry(entry_id: UUID, service: Service) -> None:
    service.dismiss(entry_id)


@router.post(
    "/sync",
    summary="Sync Letterboxd now",
    description="Reads the feed and queues its new entries for review (FR-LBX-01/02).",
    responses=error_responses({409: ["LETTERBOXD_DISABLED"], 502: ["LETTERBOXD_UNAVAILABLE"]}),
)
def sync_now(service: Service) -> SyncResult:
    return SyncResult(queued=service.sync())
