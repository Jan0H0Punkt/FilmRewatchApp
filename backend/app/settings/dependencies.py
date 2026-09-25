"""FastAPI dependency providers for the settings module (DESIGN §5.1).

Wires the layer chain for injection into the routes: request-scoped session →
:class:`SettingsRepository` → :class:`SettingsService`. The router only ever
depends on the service (a router never imports a repository).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.settings.repository import SettingsRepository
from app.settings.service import SettingsService


def get_settings_repository(
    session: Annotated[Session, Depends(get_session)],
) -> SettingsRepository:
    """Repository bound to the request's session."""
    return SettingsRepository(session)


def get_settings_service(
    repository: Annotated[SettingsRepository, Depends(get_settings_repository)],
) -> SettingsService:
    """Service over the request's repository (the seam tests override)."""
    return SettingsService(repository)
