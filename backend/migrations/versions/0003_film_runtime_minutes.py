"""films.runtime_minutes (REQ §4.1)

Adds the required ``runtime_minutes`` column. Backfilled with a placeholder
default so the NOT NULL constraint can apply to any pre-existing rows; the
default is then dropped so every future insert must supply a real value
(FR-LIB-01), matching how the Pydantic schema treats it as required.

Revision ID: 0003_film_runtime_minutes
Revises: 0002_domain_schema
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_film_runtime_minutes"
down_revision: str | None = "0002_domain_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "films",
        sa.Column("runtime_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("films", "runtime_minutes", server_default=None)


def downgrade() -> None:
    op.drop_column("films", "runtime_minutes")
