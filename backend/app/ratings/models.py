"""SQLAlchemy ORM models for the ratings module (DESIGN §5.2, REQ §4.2).

``rating_entries`` — one row per rating *event*. A film's rating history lives
in its own table (not packed into the film row) so it can be queried and
constrained independently (§5.2), and the film's ``average_rating`` is computed
from these rows on every read, never stored (FR-RAT-09/10, NFR-INT-01).

``ON DELETE CASCADE`` on ``film_id`` implements the §4.5 rule that deleting a
film deletes its whole history (NFR-INT-02). The inverse invariant — a film
must always keep ≥ 1 rating, so deleting the *last* entry deletes the film
(FR-RAT-07, §5.3) — is service-layer behaviour (M1 PR7).

Value rules (0.5-5.0 in 0.5 steps, no future ``watch_date``) are §5.4 schema/
service validation, deliberately not duplicated as CHECK constraints. Same-day
repeat ratings are allowed (FR-RAT-04), so ``(film_id, watch_date)`` is
intentionally **not** unique.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utc_now() -> datetime:
    """Timezone-aware UTC timestamp default (REQ §4.2)."""
    return datetime.now(UTC)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
