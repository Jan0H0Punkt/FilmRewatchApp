"""FastAPI dependency providers for the rewatch module (DESIGN §5.1).

Wires the layer chain for injection into the route: request-scoped session →
:class:`RewatchRepository` → :class:`RewatchService`. The router only ever
depends on the service.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.rewatch.repository import RewatchRepository
from app.rewatch.service import RewatchService


def get_rewatch_repository(session: Annotated[Session, Depends(get_session)]) -> RewatchRepository:
    """Repository bound to the request's session."""
    return RewatchRepository(session)


def get_rewatch_service(
    repository: Annotated[RewatchRepository, Depends(get_rewatch_repository)],
) -> RewatchService:
    """Service over the request's repository (the seam tests override)."""
    return RewatchService(repository)
