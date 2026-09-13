"""film_genres.position (DESIGN §5.2, REQ §4.4)

The repo owner orders a film's genres himself (most important first, e.g.
"Action, Comedy, Adventure, Comic") rather than alphabetically. Adds the
required ``position`` column to the join table.

Backfilled per film with the row's current alphabetical rank
(``row_number() over (partition by film_id order by lower(genres.name))``),
so existing data keeps its present on-screen order — nothing visibly
reorders — until the owner reorders it explicitly. Column added nullable
first so the backfill can run, then tightened to NOT NULL.

Revision ID: 0005_film_genre_position
Revises: 0004_optional_rating_value
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_film_genre_position"
down_revision: str | None = "0004_optional_rating_value"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("film_genres", sa.Column("position", sa.Integer(), nullable=True))
    op.execute(
        sa.text("""
            UPDATE film_genres
            SET position = ranked.position
            FROM (
                SELECT
                    film_id,
                    genre_id,
                    row_number() OVER (
                        PARTITION BY film_id ORDER BY lower(genres.name)
                    ) - 1 AS position
                FROM film_genres
                JOIN genres ON genres.id = film_genres.genre_id
            ) AS ranked
            WHERE ranked.film_id = film_genres.film_id
              AND ranked.genre_id = film_genres.genre_id
        """)
    )
    op.alter_column("film_genres", "position", nullable=False)


def downgrade() -> None:
    op.drop_column("film_genres", "position")
