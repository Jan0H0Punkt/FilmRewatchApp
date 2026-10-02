"""Presentation layer for the settings module (DESIGN §5.1, §5.3, FR-RW-08, FR-RW-09).

Two routes under ``/api/v1/settings``: read the single row, replace it. The
range validation (share 0-100 in steps of 10, pace >= 1) happens in :class:`SettingsBody`
before the service ever sees an out-of-range value; the DB's CHECK constraint
is the backstop.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.errors import error_responses
from app.settings.dependencies import get_settings_service
from app.settings.schemas import SettingsBody
from app.settings.service import SettingsService

router = APIRouter()


@router.get(
    "",
    summary="Get settings",
    description="The stored app settings, the rewatch share and watch pace (FR-RW-08, FR-RW-09).",
)
def read_settings(
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> SettingsBody:
    return SettingsBody.model_validate(service.get())


@router.put(
    "",
    summary="Replace settings",
    description="Replaces the stored settings and returns the stored state (FR-RW-08).",
    responses=error_responses({422: ["VALIDATION_ERROR"]}),
)
def replace_settings(
    body: SettingsBody,
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> SettingsBody:
    return SettingsBody.model_validate(service.update(body.rewatch_share, body.watch_interval_days))
