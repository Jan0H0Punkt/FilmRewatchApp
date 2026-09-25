"""film.poster_palette (DESIGN §5.2, FR-LIB-13/14)

Adds the server-derived Material 3 seed palette (up to 4 "#rrggbb" entries,
ranked by dominance) computed from the poster image. Nullable, no server
default — mirrors ``letterboxd_url``/``poster_image`` rather than ``owned``,
since there is no meaningful non-null default to backfill existing rows with
(that runs separately, see ``app.films.backfill_poster_palettes``).

Revision ID: 0010_film_poster_palette
Revises: 0009_settings
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_film_poster_palette"
down_revision: str | None = "0009_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "films", sa.Column("poster_palette", sa.ARRAY(sa.String(length=7)), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("films", "poster_palette")
