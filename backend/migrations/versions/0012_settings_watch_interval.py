"""settings_watch_interval (DESIGN §5.2, FR-RW-09)

Adds the nullable ``watch_interval_days`` (watch pace) to the single-row
settings table; ``NULL`` (Off) is the default, so the seeded row needs no backfill.

Revision ID: 0012_settings_watch_interval
Revises: 0011_letterboxd_entries
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_settings_watch_interval"
down_revision: str | None = "0011_letterboxd_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("watch_interval_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_settings_watch_interval_days_min", "settings", "watch_interval_days >= 1"
    )


def downgrade() -> None:
    op.drop_constraint("ck_settings_watch_interval_days_min", "settings", type_="check")
    op.drop_column("settings", "watch_interval_days")
