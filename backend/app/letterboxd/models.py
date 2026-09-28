"""Letterboxd review-list table (REQ §5.7, FR-LBX-02/05).

Every new feed entry is stored here until the user resolves it. Resolved rows
are kept forever: their ``guid`` is what stops the next sync (FR-LBX-02).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class LetterboxdEntry(Base):
    """One Letterboxd diary entry awaiting (or past) the user's review."""

    __tablename__ = "letterboxd_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    guid: Mapped[str] = mapped_column(String(100), unique=True)
    film_title: Mapped[str] = mapped_column(String(255))
    film_year: Mapped[int] = mapped_column(Integer)
    film_url: Mapped[str] = mapped_column(String(2048))
    watched_date: Mapped[date] = mapped_column(Date)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    rewatch: Mapped[bool] = mapped_column(Boolean)
    # The sync's match when exactly one film fitted (FR-LBX-04); nulled if that
    # film is deleted before the review.
    suggested_film_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("films.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    # NULL = open. Set by approve/assign, dismiss, or auto-resolve (FR-LBX-06/07).
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
