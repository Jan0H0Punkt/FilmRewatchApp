"""empty baseline — no domain tables (M0 PR4)

Establishes Alembic's version history with an empty baseline. Applying it
creates only the ``alembic_version`` table; the seven domain tables arrive in
M1 (DESIGN §5.2). Keeping a real (if empty) head means M1's first migration has
a parent to build on and ``alembic upgrade head`` is meaningful from M0.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-22
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Empty baseline — no schema changes."""


def downgrade() -> None:
    """Empty baseline — nothing to undo."""
