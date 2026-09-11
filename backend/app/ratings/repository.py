"""Data-access layer for the ratings module (DESIGN §5.1, M1 PR4).

CRUD over the SQLAlchemy ORM behind a stable interface; no business rules, no
HTTP. The service depends on the
:class:`~app.ratings.service.RatingRepositoryProtocol` interface, which this
class satisfies structurally.

Transaction control stays with the caller: nothing here commits. The film
create flow (PR4) adds the mandatory first entry inside its atomic unit of
work; the standalone rating lifecycle arrives in PR7.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ratings.models import RatingEntry


class RatingRepository:
    """SQLAlchemy-backed rating data access (one instance per request session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: RatingEntry) -> None:
        """Stage a new rating entry in the caller's unit of work."""
        self._session.add(entry)

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]:
        """One film's rating history, most recent ``watch_date`` first.

        The FR-RAT-05/06 ordering; entries sharing a ``watch_date`` (allowed,
        FR-RAT-04) tie-break on ``created_at`` descending so the newest recorded
        entry leads.
        """
        statement = (
            select(RatingEntry)
            .where(RatingEntry.film_id == film_id)
            .order_by(RatingEntry.watch_date.desc(), RatingEntry.created_at.desc())
        )
        return self._session.scalars(statement).all()
