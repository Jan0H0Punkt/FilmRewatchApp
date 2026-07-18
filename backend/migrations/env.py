"""Alembic migration environment (DESIGN §5.2 plumbing, M0 PR4).

Wires Alembic to the application's SQLAlchemy :class:`~app.core.db.Base` and
reads ``DATABASE_URL`` from the app config (NFR-MAINT-04) rather than from
``alembic.ini`` — so no connection string is hardcoded.

Importing the feature modules' ``models`` below registers the seven §5.2
domain tables on ``Base.metadata`` (M1 PR1), which is what ``--autogenerate``
compares against the database — after ``upgrade head`` the diff must be empty.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

import app.films.models
import app.genres.models
import app.ratings.models
import app.tags.models  # noqa: F401  (registers tags + film_tags)
from app.core.config import get_settings
from app.core.db import Base

# Alembic Config object, providing access to the values within alembic.ini.
config = context.config

# Configure Python logging from the alembic.ini sections.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The connection URL comes straight from the app config (NFR-MAINT-04), never
# from alembic.ini. It is passed directly to ``create_engine`` below rather than
# stashed via ``config.set_main_option`` — Alembic's ConfigParser treats ``%`` as
# interpolation syntax and would choke on a percent-encoded password.

# Populated by the model imports above — the seven §5.2 tables (M1 PR1).
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit migrations as SQL without a live DB connection (`--sql` mode)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = create_engine(get_settings().database_url, poolclass=NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
