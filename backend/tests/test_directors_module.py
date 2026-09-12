"""Tests for the directors module (REQ §4.1, FR-TAG-01..04 analogues).

Directors are a shared entity like tags and genres, so this mirrors
``test_genres_module.py`` with the director-specific bound (1-255 chars) and
the one structural difference: credit links are **ordered**, and a film's list
is replaced wholesale rather than one entry at a time.

Service rules run offline against a fake; link behaviour runs against real
Postgres via the PR2 harness. There is no lookup route to exercise — nothing
asks to browse directors by prefix yet.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.directors.models import Director, FilmDirector
from app.directors.repository import DirectorRepository
from app.directors.service import DirectorService, InvalidDirectorNameError
from app.films.models import Film

# --------------------------------------------------------------------------- #
# Service rules — offline, against a fake repository (§9)
# --------------------------------------------------------------------------- #


class FakeDirectorRepository:
    """In-memory :class:`DirectorRepositoryProtocol` implementation."""

    def __init__(self) -> None:
        self.by_lower_name: dict[str, Director] = {}
        self.deleted_orphans = 0
        self.links: dict[tuple[uuid.UUID, uuid.UUID], int] = {}

    def get_or_create(self, name: str) -> Director:
        key = name.lower()
        if key not in self.by_lower_name:
            self.by_lower_name[key] = Director(
                id=uuid.uuid4(), name=name, created_at=datetime.now(UTC)
            )
        return self.by_lower_name[key]

    def delete_orphans(self) -> int:
        return self.deleted_orphans

    def link_film(self, film_id: uuid.UUID, director_id: uuid.UUID, position: int) -> None:
        self.links[(film_id, director_id)] = position

    def unlink_all(self, film_id: uuid.UUID) -> None:
        self.links = {key: at for key, at in self.links.items() if key[0] != film_id}

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Director]:
        credited = [
            (self.links[(film_id, row.id)], row)
            for row in self.by_lower_name.values()
            if (film_id, row.id) in self.links
        ]
        return [row for _, row in sorted(credited, key=lambda pair: pair[0])]


def test_service_trims_surrounding_whitespace_before_storing() -> None:
    service = DirectorService(FakeDirectorRepository())
    assert service.get_or_create("  Michael Mann  ").name == "Michael Mann"


def test_service_rejects_blank_and_whitespace_only_names() -> None:
    service = DirectorService(FakeDirectorRepository())
    for bad in ("", "   ", "\t\n"):
        with pytest.raises(InvalidDirectorNameError):
            service.get_or_create(bad)


def test_service_enforces_the_255_char_bound_after_trimming() -> None:
    # REQ §4.1: 1-255 characters — the widest of the three label-ish bounds.
    service = DirectorService(FakeDirectorRepository())
    assert service.get_or_create(" " + "x" * 255 + " ").name == "x" * 255
    with pytest.raises(InvalidDirectorNameError):
        service.get_or_create("x" * 256)


def test_invalid_name_maps_to_the_validation_error_envelope_contract() -> None:
    # NFR-MAINT-03: the AppError subclass carries the stable code + status the
    # single envelope handler renders.
    error = InvalidDirectorNameError()
    assert error.code == "VALIDATION_ERROR"
    assert error.status_code == 422


def test_service_credits_in_order_and_drops_the_whole_list_at_once() -> None:
    repository = FakeDirectorRepository()
    service = DirectorService(repository)
    film_id = uuid.uuid4()
    for position, name in enumerate(("Lana Wachowski", "Lilly Wachowski")):
        service.assign(film_id, service.get_or_create(name).id, position)

    assert [row.name for row in service.list_for_film(film_id)] == [
        "Lana Wachowski",
        "Lilly Wachowski",
    ]

    service.unassign_all(film_id)
    assert service.list_for_film(film_id) == []


# --------------------------------------------------------------------------- #
# Repository behaviour — real Postgres via the PR2 harness (§9)
# --------------------------------------------------------------------------- #


def _film(natural_key: str) -> Film:
    """A film row with only the DB-required columns — enough to hang links off."""
    return Film(
        id=uuid.uuid4(),
        natural_key=natural_key,
        release_year=1999,
        runtime_minutes=136,
    )


def test_get_or_create_creates_then_reuses_case_insensitively(db_session: Session) -> None:
    repository = DirectorRepository(db_session)
    created = repository.get_or_create("Michael Mann")
    db_session.flush()
    reused = repository.get_or_create("michael MANN")
    # One row however cased, original casing preserved — the whole point of a
    # shared entity: two films by the same person share one row.
    assert reused.id == created.id
    assert reused.name == "Michael Mann"


def test_credits_are_scoped_to_their_film_and_ordered_by_position(db_session: Session) -> None:
    repository = DirectorRepository(db_session)
    films = [_film("matrix|1999|lana wachowski,lilly wachowski"), _film("heat|1995|michael mann")]
    db_session.add_all(films)
    db_session.flush()
    lana = repository.get_or_create("Lana Wachowski")
    lilly = repository.get_or_create("Lilly Wachowski")
    mann = repository.get_or_create("Michael Mann")
    db_session.flush()

    # Credited out of alphabetical order on purpose: position decides.
    repository.link_film(films[0].id, lilly.id, 1)
    repository.link_film(films[0].id, lana.id, 0)
    repository.link_film(films[1].id, mann.id, 0)

    assert [row.name for row in repository.list_for_film(films[0].id)] == [
        "Lana Wachowski",
        "Lilly Wachowski",
    ]
    assert [row.name for row in repository.list_for_film(films[1].id)] == ["Michael Mann"]


def test_unlink_all_clears_one_films_credits_only(db_session: Session) -> None:
    repository = DirectorRepository(db_session)
    films = [_film("first|1999|shared person"), _film("second|1999|shared person")]
    db_session.add_all(films)
    db_session.flush()
    shared = repository.get_or_create("Shared Person")
    db_session.flush()
    repository.link_film(films[0].id, shared.id, 0)
    repository.link_film(films[1].id, shared.id, 0)

    repository.unlink_all(films[0].id)

    assert repository.list_for_film(films[0].id) == []
    assert [row.name for row in repository.list_for_film(films[1].id)] == ["Shared Person"]


def test_delete_orphans_spares_directors_still_credited(db_session: Session) -> None:
    repository = DirectorRepository(db_session)
    film = _film("orphan probe|1999|credited person")
    db_session.add(film)
    db_session.flush()
    credited = repository.get_or_create("Credited Person")
    repository.get_or_create("Forgotten One")
    repository.get_or_create("Forgotten Two")
    db_session.flush()
    db_session.add(FilmDirector(film_id=film.id, director_id=credited.id, position=0))
    db_session.flush()

    # FR-TAG-04 analogue: a director never exists standalone.
    assert repository.delete_orphans() == 2
    assert repository.find_by_name("Credited Person") is not None
    assert repository.find_by_name("Forgotten One") is None
