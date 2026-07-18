"""SQLAlchemy ORM models for the films module (DESIGN §5.2, REQ §4.1).

Two of the seven M1 tables live here: ``films`` — the central entity — and
``titles``, a film's one-or-more titles broken out into their own table so the
title rules can be constrained independently (§5.2).

What the database stores vs. computes (§5.2):

- ``natural_key`` **is** a column (it backs the "no duplicate films" rule via a
  unique constraint, FR-LIB-04/05) but is derived by the service layer from
  primary title + release year + director — it never appears in any request or
  response schema.
- ``average_rating`` is **not** a column: it is computed from ``rating_entries``
  on every read (FR-RAT-09/10, NFR-INT-01).

Database-enforced title rules (§4.1, §5.2): **at most one primary** and **at
most one original** title per film, via partial unique indexes on ``film_id``.
The "at least one" halves (≥1 title, the primary among them) cannot be
expressed as row constraints and are the service layer's job (M1 PR4+).

Value-range rules (year range, lengths beyond column width) are §5.4 schema/
service concerns, deliberately **not** duplicated as CHECK constraints.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utc_now() -> datetime:
    """Timezone-aware UTC timestamp default (REQ §4.1 ISO-8601 UTC timestamps)."""
    return datetime.now(UTC)


class Film(Base):
    """One unique motion picture in the library (REQ §4.1)."""

    __tablename__ = "films"

    # Surrogate id; client-supplied ids arrive with the M6 sync queue, so the
    # default is generated app-side rather than by the database (§5.5 note).
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Derived duplicate-detection key (FR-LIB-04): lowercase(trim(primary_title))
    # |release_year|lowercase(trim(director)). Unique — the §5.2 "no duplicate
    # films" rule. 600 leaves headroom over the 255+1+4+1+255 worst case (some
    # Unicode lowercasing expands).
    natural_key: Mapped[str] = mapped_column(String(600), unique=True)
    release_year: Mapped[int] = mapped_column(Integer)
    director: Mapped[str] = mapped_column(String(255))
    # Optional user-entered poster URL, ≤ 2048 chars (FR-LIB-13/14).
    poster_image: Mapped[str | None] = mapped_column(String(2048))
    # Rewatch-engine inputs (REQ §4.1): columns land in M1, their consumer is M4.
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


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


# The database half of the §4.1 title rules (§5.2): a partial unique index on
# ``film_id`` makes a second primary — or a second original — title for the
# same film unrepresentable. The predicates are ``text()`` (not the mapped
# attributes) so Alembic autogenerate can render and compare them.
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
