"""Directors module tables (DESIGN §5.2, REQ §4.1).

A film may be co-directed, so directors are modelled exactly like tags and
genres: one shared row per distinct person, many-to-many to films. A name is
therefore stored once and reused, which keeps casing consistent across the
library and makes "every film by this director" a join rather than a text match.

The one departure from the label tables: the join row carries a ``position``,
because a director list is *ordered* — first-credited is information a set of
links would lose. Tag and genre links have no such order (they list
alphabetically).

A director never exists standalone — the service layer does implicit
get-or-create and orphan cleanup (FR-TAG-01/04 analogues). The 1-255 name
length is REQ §4.1 validation; the column width only matches it.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class Director(Base):
    """A director shared across films (REQ §4.1)."""

    __tablename__ = "directors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FilmDirector(Base):
    """Film ↔ director association row (§5.2 join table, NFR-INT-02).

    ``position`` is the film's credited order for this director — scoped to the
    film, not global: the same person can be first-credited on one film and
    second on another.
    """

    __tablename__ = "film_directors"

    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), primary_key=True
    )
    director_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)


# Case-insensitive uniqueness (§5.2, FR-TAG-02 analogue). An expression index,
# because Postgres unique *constraints* cannot be built over ``lower(name)``.
Index("uq_directors_name_lower", func.lower(Director.name), unique=True)
