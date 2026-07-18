"""domain schema — the seven §5.2 tables (M1 PR1)

Creates the core-domain schema on top of the empty M0 baseline: ``films`` +
``titles``, ``rating_entries``, ``tags`` + ``film_tags``, ``genres`` +
``film_genres`` (DESIGN §5.2, REQ §4.1-4.5), with every rule the database can
enforce:

- unique ``natural_key`` on ``films`` (no duplicate films, FR-LIB-04/05)
- unique indexes on ``lower(name)`` for ``tags`` and ``genres`` (FR-TAG-02)
- partial unique indexes: at most one primary and at most one original title
  per film (§4.1 title rules)
- ``ON DELETE CASCADE`` foreign keys on ``titles``, ``rating_entries``,
  ``film_tags``, ``film_genres`` (§4.5, NFR-INT-02)

No ``average_rating`` column — computed on read (NFR-INT-01). Value-range
rules (rating steps, year range) stay schema/service concerns (§5.4), not
CHECK constraints.

Revision ID: 0002_domain_schema
Revises: 0001_baseline
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_domain_schema"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the seven domain tables, constraints first-class (§5.2)."""
    op.create_table(
        "films",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("natural_key", sa.String(length=600), nullable=False),
        sa.Column("release_year", sa.Integer(), nullable=False),
        sa.Column("director", sa.String(length=255), nullable=False),
        sa.Column("poster_image", sa.String(length=2048), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("natural_key"),
    )
    op.create_table(
        "titles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("is_original", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_titles_film_id"), "titles", ["film_id"], unique=False)
    op.create_index(
        "uq_titles_one_primary_per_film",
        "titles",
        ["film_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.create_index(
        "uq_titles_one_original_per_film",
        "titles",
        ["film_id"],
        unique=True,
        postgresql_where=sa.text("is_original"),
    )
    op.create_table(
        "rating_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.Numeric(precision=2, scale=1), nullable=False),
        sa.Column("watch_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rating_entries_film_id"), "rating_entries", ["film_id"], unique=False)
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_tags_name_lower", "tags", [sa.literal_column("lower(name)")], unique=True)
    op.create_table(
        "film_tags",
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("film_id", "tag_id"),
    )
    op.create_table(
        "genres",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_genres_name_lower", "genres", [sa.literal_column("lower(name)")], unique=True
    )
    op.create_table(
        "film_genres",
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("genre_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["genre_id"], ["genres.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("film_id", "genre_id"),
    )


def downgrade() -> None:
    """Drop the seven tables — back to the empty M0 baseline."""
    op.drop_table("film_genres")
    op.drop_index("uq_genres_name_lower", table_name="genres")
    op.drop_table("genres")
    op.drop_table("film_tags")
    op.drop_index("uq_tags_name_lower", table_name="tags")
    op.drop_table("tags")
    op.drop_index(op.f("ix_rating_entries_film_id"), table_name="rating_entries")
    op.drop_table("rating_entries")
    op.drop_index("uq_titles_one_original_per_film", table_name="titles")
    op.drop_index("uq_titles_one_primary_per_film", table_name="titles")
    op.drop_index(op.f("ix_titles_film_id"), table_name="titles")
    op.drop_table("titles")
    op.drop_table("films")
