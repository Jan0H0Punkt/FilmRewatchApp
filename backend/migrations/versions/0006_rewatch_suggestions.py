"""rewatch_suggestions projection (DESIGN §5.2, §5.8)

The stored output of the once-daily rewatch job, served verbatim by
``GET /api/v1/rewatch-suggestions``. Created empty: the first scheduler run
after startup populates it.

Revision ID: 0006_rewatch_suggestions
Revises: 0005_film_genre_position
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_rewatch_suggestions"
down_revision: str | None = "0005_film_genre_position"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rewatch_suggestions",
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("days_until_next_rewatch", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("film_id"),
    )


def downgrade() -> None:
    op.drop_table("rewatch_suggestions")
