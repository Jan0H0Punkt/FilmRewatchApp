"""Tests for the genres module (M1 PR3 — FR-TAG-01..04/06 analogues, REQ §4.4).

Genres are modelled identically to tags (REQ §4.4), so this mirrors
``test_tags_module.py`` with the genre-specific bound (1-100 chars): service
rules offline against a fake, repository behaviour against real Postgres via
the PR2 harness, and the lookup route end to end.
"""

import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.db import get_session
from app.films.models import Film
from app.genres.models import FilmGenre, Genre
from app.genres.repository import GenreRepository
from app.genres.service import GenreService, InvalidGenreNameError
from app.main import create_app

# --------------------------------------------------------------------------- #
# Service rules — offline, against a fake repository (§9)
# --------------------------------------------------------------------------- #


class FakeGenreRepository:
    """In-memory :class:`GenreRepositoryProtocol` implementation."""

    def __init__(self) -> None:
        self.by_lower_name: dict[str, Genre] = {}
        self.deleted_orphans = 0
        self.links: set[tuple[uuid.UUID, uuid.UUID]] = set()

    def get_or_create(self, name: str) -> Genre:
        key = name.lower()
        if key not in self.by_lower_name:
            self.by_lower_name[key] = Genre(
                id=uuid.uuid4(), name=name, created_at=datetime.now(UTC)
            )
        return self.by_lower_name[key]

    def list_by_prefix(self, prefix: str | None = None) -> Sequence[Genre]:
        rows = sorted(self.by_lower_name.values(), key=lambda genre: genre.name.lower())
        if prefix:
            rows = [genre for genre in rows if genre.name.lower().startswith(prefix.lower())]
        return rows

    def delete_orphans(self) -> int:
        return self.deleted_orphans

    def link_film(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None:
        self.links.add((film_id, genre_id))

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Genre]:
        linked = [
            genre for genre in self.by_lower_name.values() if (film_id, genre.id) in self.links
        ]
        return sorted(linked, key=lambda genre: genre.name.lower())


def test_service_trims_surrounding_whitespace_before_storing() -> None:
    service = GenreService(FakeGenreRepository())
    assert service.get_or_create("  Science Fiction  ").name == "Science Fiction"


def test_service_rejects_blank_and_whitespace_only_names() -> None:
    service = GenreService(FakeGenreRepository())
    for bad in ("", "   ", "\t\n"):
        with pytest.raises(InvalidGenreNameError):
            service.get_or_create(bad)


def test_service_enforces_the_100_char_bound_after_trimming() -> None:
    # REQ §4.4: 1-100 characters — genres get the wider bound.
    service = GenreService(FakeGenreRepository())
    assert service.get_or_create(" " + "x" * 100 + " ").name == "x" * 100
    with pytest.raises(InvalidGenreNameError):
        service.get_or_create("x" * 101)


def test_invalid_name_maps_to_the_validation_error_envelope_contract() -> None:
    # NFR-MAINT-03: the AppError subclass carries the stable code + status the
    # single envelope handler renders.
    error = InvalidGenreNameError()
    assert error.code == "VALIDATION_ERROR"
    assert error.status_code == 422


def test_service_passes_the_prefix_through_and_reports_orphan_count() -> None:
    repository = FakeGenreRepository()
    service = GenreService(repository)
    service.get_or_create("Drama")
    service.get_or_create("Documentary")
    assert [genre.name for genre in service.list_by_prefix("do")] == ["Documentary"]
    repository.deleted_orphans = 2
    assert service.delete_orphans() == 2


# --------------------------------------------------------------------------- #
# Repository behaviour — real Postgres via the PR2 harness (§9)
# --------------------------------------------------------------------------- #


class RaceLosingGenreRepository(GenreRepository):
    """Pre-check misses once, simulating a concurrent creator winning the race."""

    missed_once = False

    def find_by_name(self, name: str) -> Genre | None:
        if not self.missed_once:
            self.missed_once = True
            return None
        return super().find_by_name(name)


def test_get_or_create_creates_then_reuses_case_insensitively(db_session: Session) -> None:
    repository = GenreRepository(db_session)
    created = repository.get_or_create("Thriller")
    db_session.flush()
    reused = repository.get_or_create("tHrIlLeR")
    # FR-TAG-01/02 analogues: one row however cased, original casing preserved.
    assert reused.id == created.id
    assert reused.name == "Thriller"


def test_get_or_create_recovers_after_losing_the_insert_race(db_session: Session) -> None:
    # A concurrent creator has already inserted the row, but our pre-check ran
    # before it was visible (the simulated race): the insert hits the unique
    # lower(name) index, the savepoint rolls back, and the winner is returned —
    # without poisoning the enclosing transaction.
    db_session.add(Genre(name="Thriller"))
    db_session.flush()
    repository = RaceLosingGenreRepository(db_session)
    won = repository.get_or_create("thriller")
    assert won.name == "Thriller"
    # The enclosing transaction survived the rolled-back savepoint: further
    # work in the same transaction still commits fine.
    db_session.add(Genre(name="Epic"))
    db_session.commit()


def test_list_by_prefix_filters_case_insensitively_and_sorts(db_session: Session) -> None:
    repository = GenreRepository(db_session)
    for name in ("Documentary", "Drama", "Comedy"):
        repository.get_or_create(name)
    db_session.flush()
    assert [genre.name for genre in repository.list_by_prefix()] == [
        "Comedy",
        "Documentary",
        "Drama",
    ]
    assert [genre.name for genre in repository.list_by_prefix("DO")] == ["Documentary"]
    assert repository.list_by_prefix("zzz") == []


def test_list_by_prefix_treats_like_wildcards_literally(db_session: Session) -> None:
    repository = GenreRepository(db_session)
    for name in ("100% true crime", "100 years of cinema", "10_special", "105 minutes"):
        repository.get_or_create(name)
    db_session.flush()
    # Unescaped, "%" would match anything and "_" any one character.
    assert [genre.name for genre in repository.list_by_prefix("100%")] == ["100% true crime"]
    assert [genre.name for genre in repository.list_by_prefix("10_")] == ["10_special"]


def test_link_film_is_idempotent_and_lists_only_that_films_genres(db_session: Session) -> None:
    # FR-TAG-03 analogue via the film flows: assigning twice is a no-op (§5.5
    # natural idempotency), and the per-film listing is scoped and alphabetical.
    repository = GenreRepository(db_session)
    films = [
        Film(
            id=uuid.uuid4(),
            natural_key=f"genre link probe {n}|2001|jane doe",
            release_year=2001,
            director="Jane Doe",
        )
        for n in (1, 2)
    ]
    db_session.add_all(films)
    db_session.flush()
    drama = repository.get_or_create("Drama")
    western = repository.get_or_create("western")
    db_session.flush()

    repository.link_film(films[0].id, drama.id)
    repository.link_film(films[0].id, drama.id)  # repeat: no-op, no violation
    repository.link_film(films[0].id, western.id)
    repository.link_film(films[1].id, drama.id)

    assert [genre.name for genre in repository.list_for_film(films[0].id)] == ["Drama", "western"]
    assert [genre.name for genre in repository.list_for_film(films[1].id)] == ["Drama"]


def test_delete_orphans_spares_labels_still_linked_to_a_film(db_session: Session) -> None:
    repository = GenreRepository(db_session)
    shared = repository.get_or_create("shared")
    repository.get_or_create("orphan-one")
    repository.get_or_create("orphan-two")
    film = Film(
        id=uuid.uuid4(),
        natural_key="genre cleanup probe|2001|jane doe",
        release_year=2001,
        director="Jane Doe",
    )
    db_session.add(film)
    db_session.flush()
    db_session.add(FilmGenre(film_id=film.id, genre_id=shared.id))
    db_session.flush()

    assert repository.delete_orphans() == 2
    assert [genre.name for genre in repository.list_by_prefix()] == ["shared"]


# --------------------------------------------------------------------------- #
# The lookup route — full stack over the harness session (§5.3)
# --------------------------------------------------------------------------- #


def _client_over(db_session: Session) -> TestClient:
    """The real app with the request-scoped session swapped for the harness one."""
    app = create_app()

    def override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override
    return TestClient(app)


def test_get_genres_lists_all_and_filters_by_prefix(db_session: Session) -> None:
    repository = GenreRepository(db_session)
    for name in ("Documentary", "Drama", "Comedy"):
        repository.get_or_create(name)
    db_session.flush()
    client = _client_over(db_session)

    listed = cast(list[dict[str, object]], client.get("/api/v1/genres").json())
    assert [row["name"] for row in listed] == ["Comedy", "Documentary", "Drama"]
    # Strict schema shape (§5.7): exactly the REQ §4.4 fields, nothing extra.
    assert all(set(row) == {"id", "name", "created_at"} for row in listed)

    filtered = cast(
        list[dict[str, object]], client.get("/api/v1/genres", params={"prefix": "d"}).json()
    )
    assert [row["name"] for row in filtered] == ["Documentary", "Drama"]

    # An empty prefix is "no filter", not "match nothing".
    unfiltered = cast(
        list[dict[str, object]], client.get("/api/v1/genres", params={"prefix": ""}).json()
    )
    assert len(unfiltered) == 3
