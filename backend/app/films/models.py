"""Films module tables (DESIGN §5.2, REQ §4.1).

Titles are a separate table so the per-film title rules can be constrained
independently.

- ``natural_key`` is derived by the service layer from primary title + release
  year + director, and appears in no request or response schema (FR-LIB-04/05).
- ``average_rating`` is not stored: it is computed from ``rating_entries`` on
  every read (FR-RAT-09/10, NFR-INT-01).
- The "at least one title, one of them primary" rules cannot be expressed as row
  constraints; the service layer enforces them. Value ranges (year, lengths
  beyond column width) are §5.4 schema concerns, not CHECK constraints.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class Film(Base):
    """One unique motion picture in the library (REQ §4.1)."""

    __tablename__ = "films"

    # Default generated app-side, not by the database: the sync queue lets clients
    # supply their own ids (§5.5).
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Derived duplicate-detection key (FR-LIB-04): lowercase(trim(primary_title))
    # |release_year|lowercase(trim(director)). 600 leaves headroom over the
    # 255+1+4+1+255 worst case (some Unicode lowercasing expands).
    natural_key: Mapped[str] = mapped_column(String(600), unique=True)
    release_year: Mapped[int] = mapped_column(Integer)
    director: Mapped[str] = mapped_column(String(255))
    # User-entered, not fetched from a metadata provider (FR-LIB-13/14).
    poster_image: Mapped[str | None] = mapped_column(String(2048))
    # Rewatch-engine inputs (REQ §4.1).
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Title(Base):
    """One title of a film — main or alternative (REQ §4.1 Title object)."""

    __tablename__ = "titles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[str] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean)
    is_original: Mapped[bool] = mapped_column(Boolean)


# The database half of the §4.1 title rules (§5.2).
#
# Each index covers only the rows matching its ``postgresql_where`` predicate, so
# ``film_id`` has to be unique *among those rows alone*: a film can hold many
# titles, but only one with ``is_primary`` true, and only one with ``is_original``
# true. A plain unique constraint on ``(film_id, is_primary)`` would not do this —
# it would also cap the false rows at one per film.
#
# The predicates are ``text()`` (not the mapped attributes) so Alembic
# autogenerate can render and compare them. Partial indexes are Postgres-only;
# on another backend these rules fall back to the service layer.
Index(
    "uq_titles_one_primary_per_film",
    Title.film_id,
    unique=True,
    postgresql_where=text("is_primary"),
)
Index(
    "uq_titles_one_original_per_film",
    Title.film_id,
    unique=True,
    postgresql_where=text("is_original"),
)
