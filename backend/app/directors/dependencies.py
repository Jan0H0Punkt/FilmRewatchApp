"""FastAPI dependency providers for the directors module (DESIGN §5.1).

Wires the layer chain for injection: request-scoped session →
:class:`DirectorRepository` → :class:`DirectorService`. No router depends on
these yet — the film flows reach the service service-to-service (§5.1).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.directors.repository import DirectorRepository
from app.directors.service import DirectorService


def get_director_repository(
    session: Annotated[Session, Depends(get_session)],
) -> DirectorRepository:
    """Repository bound to the request's session."""
    return DirectorRepository(session)


def get_director_service(
    repository: Annotated[DirectorRepository, Depends(get_director_repository)],
) -> DirectorService:
    """Service over the request's repository (the seam the film flows reuse
    service-to-service, and tests override)."""
    return DirectorService(repository)
