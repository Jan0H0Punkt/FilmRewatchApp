"""Genres module tables (DESIGN §5.2, REQ §4.4).

Genres are free text rather than an enum, modelled exactly like tags: one shared
row per distinct label, many-to-many to films, so casing stays consistent for
exact-match filtering (FR-SF-07).

A genre never exists standalone — the service layer does implicit get-or-create
and orphan cleanup (FR-TAG-01/04 analogues). The 1-100 name length is §5.4
validation; the column width only matches it.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class Genre(Base):
    """A free-text genre label shared across films (REQ §4.4)."""

    __tablename__ = "genres"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FilmGenre(Base):
    """Film ↔ genre association row (§5.2 join table, REQ §4.5, NFR-INT-02)."""

    __tablename__ = "film_genres"

    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )


# Case-insensitive uniqueness (§5.2, FR-TAG-02 analogue). An expression index,
# because Postgres unique *constraints* cannot be built over ``lower(name)``.
Index("uq_genres_name_lower", func.lower(Genre.name), unique=True)
