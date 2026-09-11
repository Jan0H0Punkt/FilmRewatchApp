"""Tests for the tags module (M1 PR3 — FR-TAG-01..04/06, §5.1, §9).

Three layers, per the §9 strategy:

* **Service rules** run offline against an in-memory fake satisfying
  :class:`TagRepositoryProtocol` — name trimming/length (REQ §4.3) and the
  ``VALIDATION_ERROR`` mapping.
* **Repository behaviour** runs against real Postgres via the PR2 harness —
  case-insensitive get-or-create (FR-TAG-01/02) including the lost-insert-race
  recovery, prefix listing with LIKE-wildcard escaping (FR-TAG-06), and orphan
  cleanup that spares shared labels (FR-TAG-04).
* **The route** is driven end to end (router → service → repository → Postgres)
  through ``TestClient`` with the request session overridden to the harness
  session.
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
from app.main import create_app
from app.tags.models import FilmTag, Tag
from app.tags.repository import TagRepository
from app.tags.service import InvalidTagNameError, TagService

# --------------------------------------------------------------------------- #
# Service rules — offline, against a fake repository (§9)
# --------------------------------------------------------------------------- #


class FakeTagRepository:
    """In-memory :class:`TagRepositoryProtocol` implementation."""

    def __init__(self) -> None:
        self.by_lower_name: dict[str, Tag] = {}
        self.deleted_orphans = 0
        self.links: set[tuple[uuid.UUID, uuid.UUID]] = set()

    def get_or_create(self, name: str) -> Tag:
        key = name.lower()
        if key not in self.by_lower_name:
            self.by_lower_name[key] = Tag(id=uuid.uuid4(), name=name, created_at=datetime.now(UTC))
        return self.by_lower_name[key]

    def list_by_prefix(self, prefix: str | None = None) -> Sequence[Tag]:
        rows = sorted(self.by_lower_name.values(), key=lambda tag: tag.name.lower())
        if prefix:
            rows = [tag for tag in rows if tag.name.lower().startswith(prefix.lower())]
        return rows

    def delete_orphans(self) -> int:
        return self.deleted_orphans

    def link_film(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        self.links.add((film_id, tag_id))

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Tag]:
        linked = [tag for tag in self.by_lower_name.values() if (film_id, tag.id) in self.links]
        return sorted(linked, key=lambda tag: tag.name.lower())


def test_service_trims_surrounding_whitespace_before_storing() -> None:
    service = TagService(FakeTagRepository())
    assert service.get_or_create("  comfort-film  ").name == "comfort-film"


def test_service_rejects_blank_and_whitespace_only_names() -> None:
    service = TagService(FakeTagRepository())
    for bad in ("", "   ", "\t\n"):
        with pytest.raises(InvalidTagNameError):
            service.get_or_create(bad)


def test_service_enforces_the_50_char_bound_after_trimming() -> None:
    # REQ §4.3: 1-50 characters. The bound applies to the trimmed name, so a
    # 50-char label padded with whitespace is still valid.
    service = TagService(FakeTagRepository())
    assert service.get_or_create(" " + "x" * 50 + " ").name == "x" * 50
    with pytest.raises(InvalidTagNameError):
        service.get_or_create("x" * 51)


def test_invalid_name_maps_to_the_validation_error_envelope_contract() -> None:
    # NFR-MAINT-03: the AppError subclass carries the stable code + status the
    # single envelope handler renders.
    error = InvalidTagNameError()
    assert error.code == "VALIDATION_ERROR"
    assert error.status_code == 422


def test_service_passes_the_prefix_through_and_reports_orphan_count() -> None:
    repository = FakeTagRepository()
    service = TagService(repository)
    service.get_or_create("Drama")
    service.get_or_create("dark-comedy")
    assert [tag.name for tag in service.list_by_prefix("da")] == ["dark-comedy"]
    repository.deleted_orphans = 3
    assert service.delete_orphans() == 3


# --------------------------------------------------------------------------- #
# Repository behaviour — real Postgres via the PR2 harness (§9)
# --------------------------------------------------------------------------- #


class RaceLosingTagRepository(TagRepository):
    """Pre-check misses once, simulating a concurrent creator winning the race."""

    missed_once = False

    def find_by_name(self, name: str) -> Tag | None:
        if not self.missed_once:
            self.missed_once = True
            return None
        return super().find_by_name(name)


def test_get_or_create_creates_then_reuses_case_insensitively(db_session: Session) -> None:
    repository = TagRepository(db_session)
    created = repository.get_or_create("Drama")
    db_session.flush()
    reused = repository.get_or_create("dRaMa")
    # FR-TAG-01/02: one row however cased, original casing preserved.
    assert reused.id == created.id
    assert reused.name == "Drama"


def test_get_or_create_recovers_after_losing_the_insert_race(db_session: Session) -> None:
    # A concurrent creator has already inserted the row, but our pre-check ran
    # before it was visible (the simulated race): the insert hits the unique
    # lower(name) index, the savepoint rolls back, and the winner is returned —
    # without poisoning the enclosing transaction.
    db_session.add(Tag(name="Drama"))
    db_session.flush()
    repository = RaceLosingTagRepository(db_session)
    won = repository.get_or_create("drama")
    assert won.name == "Drama"
    # The enclosing transaction survived the rolled-back savepoint: further
    # work in the same transaction still commits fine.
    db_session.add(Tag(name="Epic"))
    db_session.commit()


def test_list_by_prefix_filters_case_insensitively_and_sorts(db_session: Session) -> None:
    repository = TagRepository(db_session)
    for name in ("comfort-film", "Comedy", "Drama"):
        repository.get_or_create(name)
    db_session.flush()
    assert [tag.name for tag in repository.list_by_prefix()] == [
        "Comedy",
        "comfort-film",
        "Drama",
    ]
    assert [tag.name for tag in repository.list_by_prefix("CO")] == ["Comedy", "comfort-film"]
    assert repository.list_by_prefix("zzz") == []


def test_list_by_prefix_treats_like_wildcards_literally(db_session: Session) -> None:
    repository = TagRepository(db_session)
    for name in ("100% wool", "100 dalmatians", "10_special", "105 minutes"):
        repository.get_or_create(name)
    db_session.flush()
    # Unescaped, "%" would match anything and "_" any one character.
    assert [tag.name for tag in repository.list_by_prefix("100%")] == ["100% wool"]
    assert [tag.name for tag in repository.list_by_prefix("10_")] == ["10_special"]


def test_link_film_is_idempotent_and_lists_only_that_films_tags(db_session: Session) -> None:
    # FR-TAG-03 via the film flows: assigning twice is a no-op (§5.5 natural
    # idempotency), and the per-film listing is scoped and alphabetical.
    repository = TagRepository(db_session)
    films = [
        Film(
            id=uuid.uuid4(),
            natural_key=f"link probe {n}|2001|jane doe",
            release_year=2001,
            director="Jane Doe",
        )
        for n in (1, 2)
    ]
    db_session.add_all(films)
    db_session.flush()
    drama = repository.get_or_create("Drama")
    heist = repository.get_or_create("heist")
    db_session.flush()

    repository.link_film(films[0].id, drama.id)
    repository.link_film(films[0].id, drama.id)  # repeat: no-op, no violation
    repository.link_film(films[0].id, heist.id)
    repository.link_film(films[1].id, drama.id)

    assert [tag.name for tag in repository.list_for_film(films[0].id)] == ["Drama", "heist"]
    assert [tag.name for tag in repository.list_for_film(films[1].id)] == ["Drama"]


def test_delete_orphans_spares_labels_still_linked_to_a_film(db_session: Session) -> None:
    repository = TagRepository(db_session)
    shared = repository.get_or_create("shared")
    repository.get_or_create("orphan-one")
    repository.get_or_create("orphan-two")
    film = Film(
        id=uuid.uuid4(),
        natural_key="tag cleanup probe|2001|jane doe",
        release_year=2001,
        director="Jane Doe",
    )
    db_session.add(film)
    db_session.flush()
    db_session.add(FilmTag(film_id=film.id, tag_id=shared.id))
    db_session.flush()

    assert repository.delete_orphans() == 2
    assert [tag.name for tag in repository.list_by_prefix()] == ["shared"]


# --------------------------------------------------------------------------- #
# The lookup route — full stack over the harness session (§5.3, FR-TAG-06)
# --------------------------------------------------------------------------- #


def _client_over(db_session: Session) -> TestClient:
    """The real app with the request-scoped session swapped for the harness one."""
    app = create_app()

    def override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override
    return TestClient(app)


def test_get_tags_lists_all_and_filters_by_prefix(db_session: Session) -> None:
    repository = TagRepository(db_session)
    for name in ("comfort-film", "Comedy", "Drama"):
        repository.get_or_create(name)
    db_session.flush()
    client = _client_over(db_session)

    listed = cast(list[dict[str, object]], client.get("/api/v1/tags").json())
    assert [row["name"] for row in listed] == ["Comedy", "comfort-film", "Drama"]
    # Strict schema shape (§5.7): exactly the REQ §4.3 fields, nothing extra.
    assert all(set(row) == {"id", "name", "created_at"} for row in listed)

    filtered = cast(
        list[dict[str, object]], client.get("/api/v1/tags", params={"prefix": "co"}).json()
    )
    assert [row["name"] for row in filtered] == ["Comedy", "comfort-film"]

    # An empty prefix is "no filter", not "match nothing".
    unfiltered = cast(
        list[dict[str, object]], client.get("/api/v1/tags", params={"prefix": ""}).json()
    )
    assert len(unfiltered) == 3
