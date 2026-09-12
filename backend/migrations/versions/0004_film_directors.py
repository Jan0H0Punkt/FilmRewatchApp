"""directors table — a film can have several (REQ §4.1)

Moves the single ``films.director`` column into its own child table, mirroring
``titles``: co-directed and anthology films can now name every director, in
credited order.

Existing rows migrate one-to-one (each film's lone director becomes position 0),
and ``natural_key`` is **not** rewritten: the FR-LIB-04 derivation joins the
normalised director names, which for a single director yields exactly the string
the old derivation produced. The column is widened to unbounded text all the
same, because the director part now grows with the number of directors.

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
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_directors_film_id"), "directors", ["film_id"], unique=False)
    op.execute(
        "INSERT INTO directors (id, film_id, name, position) "
        "SELECT gen_random_uuid(), id, director, 0 FROM films"
    )
    op.drop_column("films", "director")
    op.alter_column("films", "natural_key", type_=sa.String(), existing_nullable=False)


def downgrade() -> None:
    # Lossy by nature: a film with several directors keeps only the
    # first-credited one, and its natural_key is rewritten to match.
    op.add_column("films", sa.Column("director", sa.String(length=255), nullable=True))
    op.execute(
        "UPDATE films SET director = ("
        "SELECT name FROM directors WHERE directors.film_id = films.id "
        "ORDER BY position LIMIT 1)"
    )
    op.execute(
        "UPDATE films SET natural_key = split_part(natural_key, '|', 1) || '|' || "
        "split_part(natural_key, '|', 2) || '|' || lower(btrim(director))"
    )
    op.alter_column("films", "director", nullable=False)
    op.alter_column("films", "natural_key", type_=sa.String(length=600), existing_nullable=False)
    op.drop_index(op.f("ix_directors_film_id"), table_name="directors")
    op.drop_table("directors")
