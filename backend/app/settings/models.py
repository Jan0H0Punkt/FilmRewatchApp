"""Settings module table (DESIGN §5.2, FR-RW-08).

A single-row table for app-wide settings — currently just the rewatch share,
which the Rewatch view uses to cap its due list. The row is seeded by
migration ``0009_settings`` and only ever updated, never inserted or deleted
again (``id`` is pinned to ``1`` by a CHECK).
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class Settings(Base):
    """The single settings row (FR-RW-08)."""

    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_settings_id_singleton"),
        # NULL (Off) passes a SQL CHECK unevaluated, so this only ever bites a
        # set value — matching the ORM-level rule the Pydantic schema enforces.
        CheckConstraint(
            "rewatch_share BETWEEN 0 AND 100 AND rewatch_share % 10 = 0",
            name="ck_settings_rewatch_share_range_step",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    rewatch_share: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
