"""rating_entries.value becomes optional (FR-RAT-12)

Some watches are deliberately left unscored — documentaries, very old films —
and the watch itself is still worth recording. NULL carries that: the entry
keeps its ``watch_date``, only the score is absent.

NULL rather than a sentinel value on purpose. A magic 0 or -1 would sit inside
the column's 0.5-5.0 domain, and every consumer (the computed average, sorting,
filtering, the M4 rewatch payload) would have to remember to exclude it —
forget once and the average is silently wrong. NULL is skipped by aggregates
by default.

The downgrade is lossy by necessity: NOT NULL cannot be restored while unrated
rows exist, so it deletes them.

Revision ID: 0004_optional_rating_value
Revises: 0003_film_runtime_minutes
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_optional_rating_value"
down_revision: str | None = "0003_film_runtime_minutes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("rating_entries", "value", existing_type=sa.Numeric(2, 1), nullable=True)


def downgrade() -> None:
    # Unrated entries have no value to fall back to; the film they belong to
    # loses that watch (and, if it was the only one, is left rating-less —
    # the FR-LIB-03 invariant this revision's predecessor assumed).
    op.execute(sa.text("DELETE FROM rating_entries WHERE value IS NULL"))
    op.alter_column("rating_entries", "value", existing_type=sa.Numeric(2, 1), nullable=False)
