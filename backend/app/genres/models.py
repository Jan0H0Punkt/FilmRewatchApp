"""SQLAlchemy ORM models for the genres module (DESIGN §5.2, REQ §4.4).

Two of the seven M1 tables: ``genres`` and the ``film_genres`` join table.
Genres are modelled **identically to tags** (REQ §4.4): a shared entity table
holding every distinct label once, connected to films many-to-many — free text,
not an enum, so casing stays consistent for exact-match filtering (FR-SF-07)
and genres get autocomplete the same way tags do (§5.2).

Database-enforced rules (§5.2):

- *No two genres with the same name, ignoring case* → a unique index on
  ``lower(name)``.
- *Removing a film removes its genre links* → ``ON DELETE CASCADE`` on both
  join columns (§4.5, NFR-INT-02).

Like a tag, a genre never exists standalone: implicit get-or-create and
service-layer orphan cleanup arrive in M1 PR3 (FR-TAG-01/04 analogues). Name
length (1-100) is §5.4 schema/service validation; the column width matches it.
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
    """Film ↔ genre association row (§5.2 join table, REQ §4.5)."""

    __tablename__ = "film_genres"

    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )


# Case-insensitive uniqueness (§5.2, FR-TAG-02 analogue): one row per name.
Index("uq_genres_name_lower", func.lower(Genre.name), unique=True)
