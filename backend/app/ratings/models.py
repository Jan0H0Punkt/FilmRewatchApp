"""Ratings module tables (DESIGN §5.2, REQ §4.2).

One row per rating *event*. The history lives in its own table rather than packed
into the film row so it can be queried and constrained independently, and a film's
``average_rating`` is computed from these rows on every read, never stored
(FR-RAT-09/10, NFR-INT-01).

Deleting a film deletes its whole history (§4.5, NFR-INT-02). The inverse is not
symmetric: a film must always keep ≥ 1 rating, so deleting the *last* entry deletes
the film — service-layer behaviour (FR-RAT-07, §5.3).

Value rules are §5.4 schema validation, deliberately not duplicated as CHECK
constraints. Same-day repeat ratings are allowed (FR-RAT-04), so
``(film_id, watch_date)`` is intentionally **not** unique.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class RatingEntry(Base):
    """A single rating event for one film (REQ §4.2)."""

    __tablename__ = "rating_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), index=True
    )
    # 0.5-5.0 in 0.5 steps — one digit before and after the point (§5.4).
    value: Mapped[Decimal] = mapped_column(Numeric(2, 1))
    # When the film was watched — distinct from when the rating was recorded
    # (``created_at``); both are stored (REQ §4.2 note).
    watch_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
