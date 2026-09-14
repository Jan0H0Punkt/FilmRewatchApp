"""The rewatch projection table (DESIGN §5.2, §5.8).

Not a domain entity — the **stored result** of the once-daily job. One row per
currently-due film; the whole table is replaced on every run, never patched.
It is the eighth table, added after the seven §5.2 domain tables.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class RewatchSuggestion(Base):
    """One currently-due film as the last run computed it (FR-RW-03)."""

    __tablename__ = "rewatch_suggestions"

    # One row per due film, so the film id is the natural key — no surrogate.
    # The cascade keeps the projection from outliving a deleted film between
    # daily runs (NFR-INT-02).
    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), primary_key=True
    )
    # Always <= 0 by the FR-RW-03 contract; not a CHECK constraint, because the
    # algorithm — not the database — owns that rule (§5.4).
    days_until_next_rewatch: Mapped[int] = mapped_column(Integer)
    # The algorithm's order, stored rather than re-derived at read time.
    # FR-RW-04 forbids anyone downstream re-sorting, and a future algorithm may
    # order by an internal score whose ties carry meaning that
    # ``days_until_next_rewatch`` alone would lose.
    position: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
