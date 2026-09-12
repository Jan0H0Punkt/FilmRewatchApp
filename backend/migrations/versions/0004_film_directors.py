"""directors as a shared entity — a film can have several (REQ §4.1)

Replaces the single ``films.director`` column with the same shape tags and
genres use: a ``directors`` table holding each person once, and a
``film_directors`` join table — plus a ``position`` the label joins don't need,
because a credit list is ordered.

Existing rows migrate without loss: each distinct director name (compared
case-insensitively, as the unique index does) becomes one ``directors`` row, and
every film is credited to its own at position 0. ``natural_key`` is **not**
rewritten — the FR-LIB-04 derivation joins the normalised director names, which
for a single director yields exactly the string the old derivation produced. The
column is widened to unbounded text all the same, because the director part now
grows with the number of directors.

Revision ID: 0004_film_directors
Revises: 0003_film_runtime_minutes
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_film_directors"
down_revision: str | None = "0003_film_runtime_minutes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "directors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_directors_name_lower", "directors", [sa.literal_column("lower(name)")], unique=True
    )
    op.create_table(
        "film_directors",
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("director_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["director_id"], ["directors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("film_id", "director_id"),
    )
    # One row per distinct name, compared the way the unique index does; min()
    # picks a deterministic spelling when two films differ only in casing.
    op.execute(
        "INSERT INTO directors (id, name, created_at) "
        "SELECT gen_random_uuid(), min(btrim(director)), now() "
        "FROM films GROUP BY lower(btrim(director))"
    )
    op.execute(
        "INSERT INTO film_directors (film_id, director_id, position) "
        "SELECT f.id, d.id, 0 FROM films f "
        "JOIN directors d ON lower(d.name) = lower(btrim(f.director))"
    )
    op.drop_column("films", "director")
    op.alter_column("films", "natural_key", type_=sa.String(), existing_nullable=False)


def downgrade() -> None:
    # Lossy by nature: a film with several directors keeps only the
    # first-credited one, and its natural_key is rewritten to match.
    op.add_column("films", sa.Column("director", sa.String(length=255), nullable=True))
    op.execute(
        "UPDATE films SET director = ("
        "SELECT d.name FROM film_directors fd JOIN directors d ON d.id = fd.director_id "
        "WHERE fd.film_id = films.id ORDER BY fd.position LIMIT 1)"
    )
    op.execute(
        "UPDATE films SET natural_key = split_part(natural_key, '|', 1) || '|' || "
        "split_part(natural_key, '|', 2) || '|' || lower(btrim(director))"
    )
    op.alter_column("films", "director", nullable=False)
    op.alter_column("films", "natural_key", type_=sa.String(length=600), existing_nullable=False)
    op.drop_table("film_directors")
    op.drop_index("uq_directors_name_lower", table_name="directors")
    op.drop_table("directors")
