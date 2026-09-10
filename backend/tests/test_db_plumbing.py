"""Tests for the data-access plumbing (DESIGN §5.2).

Needs no database — the engine is created lazily, on first use.
"""

from app.core.db import Base, get_session
from app.films.models import Film, Title
from app.genres.models import FilmGenre, Genre
from app.ratings.models import RatingEntry
from app.tags.models import FilmTag, Tag


def test_metadata_defines_exactly_the_seven_domain_tables() -> None:
    # One table per entity/join (REQ §4.1-4.5) and nothing else: a stray model
    # would silently widen the schema. Importing the classes is what registers
    # them on ``Base.metadata``.
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
