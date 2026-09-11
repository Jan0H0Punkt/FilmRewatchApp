"""Offline tests for the films module (M1 PR4 — FR-LIB-01..05, §5.4, §9).

The service and schema rules, no database: the create schema's §5.4 shape
(title rules, bounds, strictness), natural-key derivation (FR-LIB-04), and the
:class:`FilmService` flows against in-memory fakes satisfying the §5.1
protocols — duplicate block (FR-LIB-05), client-minted ids (§5.5 note),
label dedupe, and the computed average (FR-RAT-09).

The same rules are exercised end to end (envelope and all) against real
Postgres in ``test_films_api.py``.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.films.models import Film, Title
from app.films.schemas import FilmCreate
from app.films.service import (
    DuplicateFilmError,
    FilmIdCollisionError,
    FilmNotFoundError,
    FilmService,
    derive_natural_key,
)
from app.genres.models import Genre
from app.ratings.models import RatingEntry
from app.tags.models import Tag

# --------------------------------------------------------------------------- #
# Fakes satisfying the §5.1 protocols
# --------------------------------------------------------------------------- #


def _now() -> datetime:
    return datetime.now(UTC)


class FakeFilmRepository:
    """In-memory :class:`FilmRepositoryProtocol` implementation.

    ``add_film`` stamps the timestamps the database defaults would set at
    flush time, so the detail projection is buildable offline.
    """

    def __init__(self) -> None:
        self.films: dict[uuid.UUID, Film] = {}
        self.titles: list[Title] = []
        self.commits = 0

    def add_film(self, film: Film) -> None:
        film.created_at = _now()
        film.updated_at = _now()
        film.is_favorite = False
        film.delay_days = 0
        self.films[film.id] = film

    def add_title(self, title: Title) -> None:
        self.titles.append(title)

    def find_by_id(self, film_id: uuid.UUID) -> Film | None:
        return self.films.get(film_id)

    def find_by_natural_key(self, natural_key: str) -> Film | None:
        return next((film for film in self.films.values() if film.natural_key == natural_key), None)

    def list_titles(self, film_id: uuid.UUID) -> Sequence[Title]:
        rows = [title for title in self.titles if title.film_id == film_id]
        return sorted(rows, key=lambda title: (not title.is_primary, title.value.lower()))

    def commit(self) -> None:
        self.commits += 1


class FakeTagService:
    """In-memory :class:`TagAssignmentProtocol` implementation."""

    def __init__(self) -> None:
        self.by_lower: dict[str, Tag] = {}
        self.links: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.assign_calls = 0

    def get_or_create(self, name: str) -> Tag:
        trimmed = name.strip()
        key = trimmed.lower()
        if key not in self.by_lower:
            self.by_lower[key] = Tag(id=uuid.uuid4(), name=trimmed, created_at=_now())
        return self.by_lower[key]

    def assign(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        self.assign_calls += 1
        self.links.add((film_id, tag_id))

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Tag]:
        linked = [tag for tag in self.by_lower.values() if (film_id, tag.id) in self.links]
        return sorted(linked, key=lambda tag: tag.name.lower())


class FakeGenreService:
    """In-memory :class:`GenreAssignmentProtocol` implementation."""

    def __init__(self) -> None:
        self.by_lower: dict[str, Genre] = {}
        self.links: set[tuple[uuid.UUID, uuid.UUID]] = set()

    def get_or_create(self, name: str) -> Genre:
        trimmed = name.strip()
        key = trimmed.lower()
        if key not in self.by_lower:
            self.by_lower[key] = Genre(id=uuid.uuid4(), name=trimmed, created_at=_now())
        return self.by_lower[key]

    def assign(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None:
        self.links.add((film_id, genre_id))

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Genre]:
        linked = [genre for genre in self.by_lower.values() if (film_id, genre.id) in self.links]
        return sorted(linked, key=lambda genre: genre.name.lower())


class FakeRatingService:
    """In-memory :class:`RatingHistoryProtocol` implementation."""

    def __init__(self) -> None:
        self.by_film: dict[uuid.UUID, list[RatingEntry]] = {}

    def add_entry(self, film_id: uuid.UUID, value: Decimal, watch_date: date) -> RatingEntry:
        entry = RatingEntry(
            id=uuid.uuid4(),
            film_id=film_id,
            value=value,
            watch_date=watch_date,
            created_at=_now(),
        )
        self.by_film.setdefault(film_id, []).append(entry)
        return entry

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[RatingEntry]:
        rows = self.by_film.get(film_id, [])
        return sorted(rows, key=lambda entry: (entry.watch_date, entry.created_at), reverse=True)


def make_service() -> tuple[FilmService, FakeFilmRepository, FakeTagService, FakeRatingService]:
    repository = FakeFilmRepository()
    tags = FakeTagService()
    ratings = FakeRatingService()
    return FilmService(repository, tags, FakeGenreService(), ratings), repository, tags, ratings


def payload(**overrides: object) -> FilmCreate:
    """A minimal valid create payload (FR-LIB-01..03), overridable per test."""
    data: dict[str, object] = {
        "titles": [{"value": "Heat", "is_primary": True}],
        "release_year": 1995,
        "director": "Michael Mann",
        "genre": ["Crime"],
        "tags": ["heist"],
        "first_rating": {"value": 4.5, "watch_date": "1995-12-15"},
    }
    data.update(overrides)
    return FilmCreate.model_validate(data)


# --------------------------------------------------------------------------- #
# Natural-key derivation (FR-LIB-04)
# --------------------------------------------------------------------------- #


def test_natural_key_normalises_case_and_surrounding_whitespace() -> None:
    key = derive_natural_key("  HEAT ", 1995, " Michael MANN  ")
    assert key == "heat|1995|michael mann"
    assert key == derive_natural_key("Heat", 1995, "Michael Mann")


# --------------------------------------------------------------------------- #
# Create-schema rules (§5.4) — strict base, title rules, bounds
# --------------------------------------------------------------------------- #


def test_a_lone_title_becomes_primary_automatically() -> None:
    # FR-LIB-01: one title, not flagged — the system designates it primary.
    created = payload(titles=[{"value": "Heat"}])
    assert created.titles[0].is_primary is True


def test_multiple_titles_require_exactly_one_primary() -> None:
    for titles in (
        [{"value": "Heat", "is_primary": True}, {"value": "Fuego", "is_primary": True}],
        [{"value": "Heat"}, {"value": "Fuego"}],
    ):
        with pytest.raises(ValidationError):
            payload(titles=titles)


def test_at_most_one_title_may_be_original() -> None:
    with pytest.raises(ValidationError):
        payload(
            titles=[
                {"value": "Heat", "is_primary": True, "is_original": True},
                {"value": "Fuego", "is_original": True},
            ]
        )


def test_mandatory_parts_cannot_be_missing_or_empty() -> None:
    # FR-LIB-01/03: ≥1 title, ≥1 genre, ≥1 tag, and the first rating itself.
    empties: list[dict[str, object]] = [{"titles": []}, {"genre": []}, {"tags": []}]
    for override in empties:
        with pytest.raises(ValidationError):
            payload(**override)
    with pytest.raises(ValidationError):
        FilmCreate.model_validate(
            {
                "titles": [{"value": "Heat"}],
                "release_year": 1995,
                "director": "Michael Mann",
                "genre": ["Crime"],
                "tags": ["heist"],
                # first_rating missing entirely
            }
        )


def test_release_year_bounds_are_1888_through_the_current_year() -> None:
    assert payload(release_year=1888).release_year == 1888
    current_year = datetime.now(UTC).year
    assert payload(release_year=current_year).release_year == current_year
    for bad_year in (1887, current_year + 1):
        with pytest.raises(ValidationError):
            payload(release_year=bad_year)


def test_rating_value_must_be_a_half_step_in_range() -> None:
    for bad_value in (0.0, 0.4, 4.3, 5.5):
        with pytest.raises(ValidationError):
            payload(first_rating={"value": bad_value, "watch_date": "1995-12-15"})


def test_watch_date_must_not_be_in_the_future() -> None:
    with pytest.raises(ValidationError):
        payload(first_rating={"value": 4.5, "watch_date": "2999-01-01"})


def test_lossy_coercion_is_rejected() -> None:
    # §5.7 strict base: "1995" is not an int.
    with pytest.raises(ValidationError):
        payload(release_year="1995")


def test_unknown_and_system_fields_are_rejected() -> None:
    # extra="forbid": natural_key never appears in a request (FR-LIB-04), and
    # is_favorite/delay_days are not accepted at create (FR-LIB-02).
    for override in (
        {"natural_key": "heat|1995|michael mann"},
        {"is_favorite": True},
        {"delay_days": 7},
    ):
        with pytest.raises(ValidationError):
            payload(**override)


def test_poster_image_must_be_a_well_formed_short_url() -> None:
    assert payload(poster_image="https://example.org/heat.jpg").poster_image is not None
    for bad_url in ("not a url", "ftp://example.org/heat.jpg", "https://" + "x" * 2050):
        with pytest.raises(ValidationError):
            payload(poster_image=bad_url)


# --------------------------------------------------------------------------- #
# Service flows against the fakes (§9)
# --------------------------------------------------------------------------- #


def test_create_persists_everything_in_one_commit_and_returns_the_projection() -> None:
    service, repository, tags, ratings = make_service()
    detail = service.create(
        payload(tags=["heist", " HEIST ", "la"], genre=["Crime", "crime", "Thriller"])
    )

    film = repository.films[detail.id]
    assert film.natural_key == "heat|1995|michael mann"
    assert repository.commits == 1
    # Payload labels deduplicated case/whitespace-insensitively before linking.
    assert sorted(tag.name for tag in tags.by_lower.values()) == ["heist", "la"]
    assert tags.assign_calls == 2
    assert len(ratings.by_film[detail.id]) == 1

    assert detail.titles[0].value == "Heat"
    assert detail.tags == ["heist", "la"]
    assert detail.genre == ["Crime", "Thriller"]
    assert detail.average_rating == 4.5
    assert detail.is_favorite is False and detail.delay_days == 0  # FR-LIB-02 defaults
    # FR-LIB-04: the derived key is absent from the projection.
    assert "natural_key" not in detail.model_dump()


def test_duplicate_create_is_blocked_identifying_the_existing_film() -> None:
    service, repository, _, _ = make_service()
    first = service.create(payload())
    with pytest.raises(DuplicateFilmError) as caught:
        service.create(payload(titles=[{"value": "  HEAT "}], director="michael mann "))

    error = caught.value
    assert error.code == "DUPLICATE_FILM"
    assert error.status_code == 409
    assert error.existing.id == first.id
    assert error.existing.primary_title == "Heat"
    assert str(first.id) in error.message and "Heat" in error.message
    assert len(repository.films) == 1  # nothing was created


def test_duplicate_check_probe_gives_the_same_verdict_without_side_effects() -> None:
    service, repository, _, _ = make_service()
    created = service.create(payload())

    hit = service.check_duplicate(" HEAT", 1995, "michael MANN ")
    assert hit.duplicate is True
    assert hit.film is not None and hit.film.id == created.id

    miss = service.check_duplicate("Heat", 1996, "Michael Mann")
    assert miss.duplicate is False and miss.film is None
    assert len(repository.films) == 1


def test_client_minted_id_is_honoured_and_a_collision_rejected() -> None:
    # §5.5 scoping note: optional client UUID; collision is a plain validation
    # error in M1 (replay semantics arrive with M6).
    service, _, _, _ = make_service()
    minted = uuid.uuid4()
    created = service.create(payload(id=str(minted)))
    assert created.id == minted

    with pytest.raises(FilmIdCollisionError) as caught:
        service.create(payload(id=str(minted), titles=[{"value": "Collateral"}]))
    assert caught.value.code == "VALIDATION_ERROR"
    assert caught.value.status_code == 422


def test_average_is_computed_from_the_full_history_and_rounds_half_up() -> None:
    service, _, _, ratings = make_service()
    created = service.create(payload())  # 4.5 on 1995-12-15
    ratings.add_entry(created.id, Decimal("4.0"), date(1995, 12, 10))

    detail = service.get_detail(created.id)
    # Most recent watch first (FR-RAT-05/06) …
    assert [entry.watch_date for entry in detail.rating_history] == [
        date(1995, 12, 15),
        date(1995, 12, 10),
    ]
    # … and (4.5 + 4.0) / 2 = 4.25 rounds half-up to one decimal (FR-RAT-09).
    assert detail.average_rating == 4.3


def test_get_detail_for_an_unknown_id_maps_to_the_not_found_envelope() -> None:
    service, _, _, _ = make_service()
    with pytest.raises(FilmNotFoundError) as caught:
        service.get_detail(uuid.uuid4())
    assert caught.value.code == "NOT_FOUND"
    assert caught.value.status_code == 404
