"""SQLAlchemy ORM models for the tags module (DESIGN §5.2, REQ §4.3).

Two of the seven M1 tables: ``tags`` — every distinct label stored exactly once
— and the ``film_tags`` many-to-many join table linking labels to films.

Database-enforced rules (§5.2):

- *No two tags with the same name, ignoring case* (FR-TAG-02: "Drama" and
  "drama" are one row) → a unique index on ``lower(name)``.
- *Removing a film removes its tag links* → ``ON DELETE CASCADE`` on both join
  columns (§4.5, NFR-INT-02).

A tag never exists standalone (FR-TAG-01): creation happens implicitly through
film payloads via the service's get-or-create, and a tag left on no films is
deleted by the service-layer orphan cleanup (FR-TAG-04) — both M1 PR3. Name
length (1-50) is §5.4 schema/service validation; the column width matches it.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class Tag(Base):
    """A user-defined label shared across films (REQ §4.3)."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FilmTag(Base):
    """Film ↔ tag association row (§5.2 join table, REQ §4.5)."""

    __tablename__ = "film_tags"

    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


# Case-insensitive uniqueness (FR-TAG-02, §5.2): one row per name however cased.
Index("uq_tags_name_lower", func.lower(Tag.name), unique=True)
