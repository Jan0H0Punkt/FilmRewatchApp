"""film.letterboxd_url (DESIGN §5.2, REQ §4.1)

Adds the optional, user-entered Letterboxd link column — same optionality and
nullability as ``poster_image``. No backfill: existing rows get ``NULL``.

Revision ID: 0007_film_letterboxd_url
Revises: 0006_rewatch_suggestions
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_film_letterboxd_url"
down_revision: str | None = "0006_rewatch_suggestions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("films", sa.Column("letterboxd_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("films", "letterboxd_url")
