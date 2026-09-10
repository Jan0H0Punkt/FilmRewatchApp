"""FastAPI dependency providers for the tags module (DESIGN §5.1, M1 PR3).

Wires the layer chain for injection into the routes: request-scoped session →
:class:`TagRepository` → :class:`TagService`. The router only ever depends on
the service (a router never imports a repository).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.tags.repository import TagRepository
from app.tags.service import TagService


def get_tag_repository(session: Annotated[Session, Depends(get_session)]) -> TagRepository:
    """Repository bound to the request's session."""
    return TagRepository(session)


def get_tag_service(
    repository: Annotated[TagRepository, Depends(get_tag_repository)],
) -> TagService:
    """Service over the request's repository (also the seam M1 PR4+ film flows
    reuse service-to-service, and tests override)."""
    return TagService(repository)
