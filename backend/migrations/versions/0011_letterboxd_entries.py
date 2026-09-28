"""letterboxd_entries (REQ §5.7)

The Letterboxd review list: every new feed entry until the user resolves it.

Revision ID: 0011_letterboxd_entries
Revises: 0010_film_poster_palette
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_letterboxd_entries"
down_revision: str | None = "0010_film_poster_palette"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "letterboxd_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guid", sa.String(length=100), nullable=False),
        sa.Column("film_title", sa.String(length=255), nullable=False),
        sa.Column("film_year", sa.Integer(), nullable=False),
        sa.Column("film_url", sa.String(length=2048), nullable=False),
        sa.Column("watched_date", sa.Date(), nullable=False),
        sa.Column("rating", sa.Numeric(precision=2, scale=1), nullable=True),
        sa.Column("rewatch", sa.Boolean(), nullable=False),
        sa.Column("suggested_film_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["suggested_film_id"], ["films.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guid"),
    )


def downgrade() -> None:
    op.drop_table("letterboxd_entries")
