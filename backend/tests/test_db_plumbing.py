"""Tests for the data-access plumbing (DESIGN §5.2, M0 PR4 / M1 PR1).

M0 shipped the SQLAlchemy/Alembic harness with an empty ``Base.metadata``; M1
PR1 registers the seven §5.2 domain tables on it. This guards the M1 invariant
at the model level: ``Base.metadata`` defines **exactly** those seven tables —
no more (a stray model would silently widen the schema), no fewer — which,
together with the 0002 migration, is what keeps ``alembic revision
--autogenerate`` an empty diff after ``upgrade head``. It needs no database
(the engine is created lazily, on first use).
"""

from app.core.db import Base, get_session
from app.films.models import Film, Title
from app.genres.models import FilmGenre, Genre
from app.ratings.models import RatingEntry
from app.tags.models import FilmTag, Tag


def test_metadata_defines_exactly_the_seven_domain_tables() -> None:
    # The §5.2 schema, one table per entity/join (REQ §4.1-4.5) — and nothing
    # else. ``average_rating`` has no table/column: computed on read (NFR-INT-01).
    # Importing the classes above is what registers them on ``Base.metadata``.
    domain_models = (Film, Title, RatingEntry, Tag, FilmTag, Genre, FilmGenre)
    assert {model.__tablename__ for model in domain_models} == {
        "films",
        "titles",
        "rating_entries",
        "tags",
        "film_tags",
        "genres",
        "film_genres",
    }
    assert set(Base.metadata.tables) == {model.__tablename__ for model in domain_models}


def test_get_session_is_a_generator_dependency() -> None:
    # The FastAPI dependency is a generator (yields then cleans up); constructing
    # it must not touch the database.
    import inspect

    assert inspect.isgeneratorfunction(get_session)
