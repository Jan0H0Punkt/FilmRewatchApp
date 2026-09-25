"""settings (DESIGN §5.2, FR-RW-08)

The single-row settings table backing the rewatch-share setting. Creates the
table and seeds the one row with ``rewatch_share = NULL`` (Off).

Revision ID: 0009_settings
Revises: 0008_film_owned
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_settings"
down_revision: str | None = "0008_film_owned"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rewatch_share", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_settings_id_singleton"),
        sa.CheckConstraint(
            "rewatch_share BETWEEN 0 AND 100 AND rewatch_share % 10 = 0",
            name="ck_settings_rewatch_share_range_step",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO settings (id, rewatch_share, updated_at) VALUES (1, NULL, now())")


def downgrade() -> None:
    op.drop_table("settings")
