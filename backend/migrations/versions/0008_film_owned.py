"""film.owned (DESIGN §5.2, REQ §4.1)

Adds the "I own this film on disc" flag. Existing rows are backfilled to
``false`` by the server default, which is then dropped so the column behaves
like ``is_favorite``: app-side default, no database-side one.

Revision ID: 0008_film_owned
Revises: 0007_film_letterboxd_url
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_film_owned"
down_revision: str | None = "0007_film_letterboxd_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("films", sa.Column("owned", sa.Boolean(), nullable=False, server_default="false"))
    op.alter_column("films", "owned", server_default=None)


def downgrade() -> None:
    op.drop_column("films", "owned")
