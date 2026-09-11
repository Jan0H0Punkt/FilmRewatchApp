"""Offline tests for the films module (M1 PR4/PR5/PR6 — FR-LIB-01..12, §5.4, §9).

The service and schema rules, no database: the create schema's §5.4 shape
(title rules, bounds, strictness), natural-key derivation (FR-LIB-04), and the
:class:`FilmService` flows against in-memory fakes satisfying the §5.1
protocols — duplicate block (FR-LIB-05), client-minted ids (§5.5 note),
label dedupe, and the computed average (FR-RAT-09). PR5 adds the edit schema
and flow (FR-LIB-06..09): immutable fields, poster set/replace/remove,
natural-key recomputation, and the duplicate block applied to edits. PR6 adds
the delete flow (FR-LIB-10..12): NOT_FOUND on an unknown id, and that both
label kinds' orphan sweeps are reached — the cascade itself is a
repository/database behaviour, verified end to end below.

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
from app.films.schemas import FilmCreate, FilmUpdate
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

    def delete_titles(self, film_id: uuid.UUID) -> None:
        self.titles = [title for title in self.titles if title.film_id != film_id]

    def delete_film(self, film: Film) -> None:
        # Mirrors the one dependent table this fake itself owns; ratings and
        # label links live in the other fakes and are, like the real FK
        # cascade, out of this repository's reach (M1 PR6).
        self.titles = [title for title in self.titles if title.film_id != film.id]
        del self.films[film.id]

    def commit(self) -> None:
        self.commits += 1


class FakeTagService:
    """In-memory :class:`TagAssignmentProtocol` implementation."""

    def __init__(self) -> None:
        self.by_lower: dict[str, Tag] = {}
        self.links: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.assign_calls = 0
        self.orphan_sweeps = 0

    def get_or_create(self, name: str) -> Tag:
        trimmed = name.strip()
        key = trimmed.lower()
        if key not in self.by_lower:
            self.by_lower[key] = Tag(id=uuid.uuid4(), name=trimmed, created_at=_now())
        return self.by_lower[key]

    def assign(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        self.assign_calls += 1
        self.links.add((film_id, tag_id))

    def unassign(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        self.links.discard((film_id, tag_id))

    def delete_orphans(self) -> int:
        self.orphan_sweeps += 1
        linked_ids = {tag_id for _, tag_id in self.links}
        orphans = [tag for tag in self.by_lower.values() if tag.id not in linked_ids]
        for tag in orphans:
            del self.by_lower[tag.name.lower()]
        return len(orphans)

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Tag]:
        linked = [tag for tag in self.by_lower.values() if (film_id, tag.id) in self.links]
        return sorted(linked, key=lambda tag: tag.name.lower())


class FakeGenreService:
    """In-memory :class:`GenreAssignmentProtocol` implementation."""

    def __init__(self) -> None:
        self.by_lower: dict[str, Genre] = {}
        self.links: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.orphan_sweeps = 0

    def get_or_create(self, name: str) -> Genre:
        trimmed = name.strip()
        key = trimmed.lower()
        if key not in self.by_lower:
            self.by_lower[key] = Genre(id=uuid.uuid4(), name=trimmed, created_at=_now())
        return self.by_lower[key]

    def assign(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None:
        self.links.add((film_id, genre_id))

    def unassign(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None:
        self.links.discard((film_id, genre_id))

    def delete_orphans(self) -> int:
        self.orphan_sweeps += 1
        linked_ids = {genre_id for _, genre_id in self.links}
        orphans = [genre for genre in self.by_lower.values() if genre.id not in linked_ids]
        for genre in orphans:
            del self.by_lower[genre.name.lower()]
        return len(orphans)

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


def make_service_with_genres() -> tuple[
    FilmService, FakeFilmRepository, FakeTagService, FakeGenreService, FakeRatingService
]:
    """Like :func:`make_service`, but also exposes the genre fake — needed by
    the delete tests to assert *both* label kinds are swept (M1 PR6)."""
    repository = FakeFilmRepository()
    tags = FakeTagService()
    genres = FakeGenreService()
    ratings = FakeRatingService()
    return FilmService(repository, tags, genres, ratings), repository, tags, genres, ratings


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


def update_payload(**fields: object) -> FilmUpdate:
    """A ``FilmUpdate`` built from only the given fields — every field left
    out stays at the schema's "absent/unchanged" default (FR-LIB-06)."""
    return FilmUpdate.model_validate(fields)


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


# --------------------------------------------------------------------------- #
# Edit-schema rules (§5.4, FR-LIB-06/07) — strict base, title rules, bounds
# --------------------------------------------------------------------------- #


def test_update_payload_with_no_fields_is_a_valid_no_op() -> None:
    assert update_payload().model_fields_set == set()


def test_update_payload_rejects_immutable_and_unknown_fields() -> None:
    # FR-LIB-07: id, created_at, natural_key, average_rating are never
    # editable — the strict base rejects them as unknown fields.
    for override in (
        {"id": str(uuid.uuid4())},
        {"created_at": "2020-01-01T00:00:00Z"},
        {"natural_key": "heat|1995|michael mann"},
        {"average_rating": 4.5},
    ):
        with pytest.raises(ValidationError):
            update_payload(**override)


def test_update_payload_titles_are_revalidated_against_the_title_rules() -> None:
    with pytest.raises(ValidationError):
        update_payload(
            titles=[
                {"value": "Heat", "is_primary": True},
                {"value": "Fuego", "is_primary": True},
            ]
        )
    with pytest.raises(ValidationError):
        update_payload(
            titles=[
                {"value": "Heat", "is_primary": True, "is_original": True},
                {"value": "Fuego", "is_original": True},
            ]
        )
    lone = update_payload(titles=[{"value": "Heat"}])
    assert lone.titles is not None and lone.titles[0].is_primary is True


def test_update_payload_cannot_clear_titles_tags_or_genres_to_empty() -> None:
    # The always-≥1 invariant (FR-LIB-01/03) survives edits: an edit can
    # reassign these lists but never empty them outright.
    empties: list[dict[str, object]] = [{"titles": []}, {"tags": []}, {"genre": []}]
    for override in empties:
        with pytest.raises(ValidationError):
            update_payload(**override)


def test_update_payload_field_bounds_match_create() -> None:
    current_year = datetime.now(UTC).year
    with pytest.raises(ValidationError):
        update_payload(release_year=current_year + 1)
    with pytest.raises(ValidationError):
        update_payload(director="   ")
    with pytest.raises(ValidationError):
        update_payload(poster_image="not a url")
    with pytest.raises(ValidationError):
        update_payload(poster_image="https://" + "x" * 2050)


def test_update_payload_null_poster_is_distinguishable_from_absent() -> None:
    # FR-LIB-15: an explicit null means "remove"; everywhere else (§5.4 note
    # on the FilmUpdate schema) null means "unchanged" — the service tells the
    # two apart via ``model_fields_set``.
    absent = update_payload()
    assert "poster_image" not in absent.model_fields_set

    explicit_null = update_payload(poster_image=None)
    assert "poster_image" in explicit_null.model_fields_set
    assert explicit_null.poster_image is None


# --------------------------------------------------------------------------- #
# Edit flow against the fakes (§9, FR-LIB-06..09)
# --------------------------------------------------------------------------- #


def test_update_unknown_film_id_maps_to_the_not_found_envelope() -> None:
    service, _, _, _ = make_service()
    with pytest.raises(FilmNotFoundError):
        service.update(uuid.uuid4(), update_payload(director="Someone Else"))


def test_update_empty_body_is_a_no_op_and_leaves_updated_at_untouched() -> None:
    service, repository, _, _ = make_service()
    created = service.create(payload())
    stored = repository.films[created.id]
    stored.updated_at = datetime(2000, 1, 1, tzinfo=UTC)  # backdated to detect any bump

    detail = service.update(created.id, update_payload())

    assert detail.model_dump(exclude={"updated_at"}) == created.model_dump(exclude={"updated_at"})
    assert detail.updated_at == datetime(2000, 1, 1, tzinfo=UTC)
    assert stored.updated_at == datetime(2000, 1, 1, tzinfo=UTC)


def test_update_bumps_updated_at_on_a_real_change_but_never_created_at() -> None:
    service, repository, _, _ = make_service()
    created = service.create(payload())
    stored = repository.films[created.id]
    stored.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    original_created_at = stored.created_at

    detail = service.update(created.id, update_payload(is_favorite=True))

    assert detail.is_favorite is True
    assert stored.updated_at > datetime(2000, 1, 1, tzinfo=UTC)
    assert stored.created_at == original_created_at


def test_update_release_year_and_director_persist_and_recompute_the_key() -> None:
    service, repository, _, _ = make_service()
    created = service.create(payload())

    detail = service.update(created.id, update_payload(release_year=1996, director="Someone Else"))

    assert detail.release_year == 1996
    assert detail.director == "Someone Else"
    assert repository.films[created.id].natural_key == derive_natural_key(
        "Heat", 1996, "Someone Else"
    )


def test_update_a_film_never_collides_with_its_own_unchanged_key() -> None:
    service, repository, _, _ = make_service()
    created = service.create(payload())

    detail = service.update(
        created.id,
        update_payload(
            titles=[{"value": "Heat", "is_primary": True}],
            release_year=1995,
            director="Michael Mann",
        ),
    )

    assert detail.id == created.id
    assert repository.films[created.id].natural_key == derive_natural_key(
        "Heat", 1995, "Michael Mann"
    )


def test_update_recomputes_natural_key_and_blocks_a_collision_leaving_the_film_unchanged() -> None:
    service, repository, _, _ = make_service()
    heat = service.create(payload())
    collateral = service.create(
        payload(titles=[{"value": "Collateral", "is_primary": True}], release_year=2004)
    )

    with pytest.raises(DuplicateFilmError) as caught:
        service.update(
            collateral.id,
            update_payload(
                titles=[{"value": "  HEAT ", "is_primary": True}],
                release_year=1995,
                director="michael mann ",
            ),
        )
    assert caught.value.existing.id == heat.id

    # Unapplied: the film is byte-for-byte as it was (FR-LIB-09).
    unchanged = repository.films[collateral.id]
    assert unchanged.release_year == 2004
    assert unchanged.natural_key == derive_natural_key("Collateral", 2004, "Michael Mann")
    titles = repository.list_titles(collateral.id)
    assert [title.value for title in titles] == ["Collateral"]


def test_update_recomputes_natural_key_when_only_the_primary_designation_changes() -> None:
    service, repository, _, _ = make_service()
    created = service.create(
        payload(
            titles=[
                {"value": "Heat", "is_primary": True},
                {"value": "Fuego", "is_original": True},
            ]
        )
    )
    assert repository.films[created.id].natural_key == derive_natural_key(
        "Heat", 1995, "Michael Mann"
    )

    service.update(
        created.id,
        update_payload(
            titles=[
                {"value": "Heat", "is_original": True},
                {"value": "Fuego", "is_primary": True},
            ]
        ),
    )

    assert repository.films[created.id].natural_key == derive_natural_key(
        "Fuego", 1995, "Michael Mann"
    )
    titles = repository.list_titles(created.id)
    assert {title.value for title in titles} == {"Heat", "Fuego"}
    primary = next(title for title in titles if title.is_primary)
    assert primary.value == "Fuego"


def test_update_poster_can_be_set_replaced_and_removed() -> None:
    service, _, _, _ = make_service()
    created = service.create(payload())
    assert created.poster_image is None

    set_ = service.update(created.id, update_payload(poster_image="https://example.org/a.jpg"))
    assert set_.poster_image == "https://example.org/a.jpg"

    replaced = service.update(created.id, update_payload(poster_image="https://example.org/b.jpg"))
    assert replaced.poster_image == "https://example.org/b.jpg"

    removed = service.update(created.id, update_payload(poster_image=None))
    assert removed.poster_image is None

    # A later edit that never mentions poster_image leaves it removed.
    untouched = service.update(created.id, update_payload(is_favorite=True))
    assert untouched.poster_image is None


def test_update_reassigns_tags_and_genres_sparing_labels_shared_with_other_films() -> None:
    service, _, tags, _ = make_service()
    solo = service.create(payload(tags=["heist"], genre=["Crime"]))
    service.create(
        payload(
            titles=[{"value": "Collateral", "is_primary": True}],
            release_year=2004,
            tags=["heist"],
            genre=["Crime"],
        )
    )

    detail = service.update(solo.id, update_payload(tags=["la"], genre=["Thriller"]))

    assert detail.tags == ["la"]
    assert detail.genre == ["Thriller"]
    assert "heist" in tags.by_lower  # still linked to the other film, survives


def test_update_removing_a_films_only_label_link_deletes_the_orphan() -> None:
    service, _, tags, _ = make_service()
    created = service.create(payload(tags=["heist"]))
    assert "heist" in tags.by_lower

    service.update(created.id, update_payload(tags=["la"]))

    assert "heist" not in tags.by_lower  # orphaned and reaped (FR-TAG-04)
    assert "la" in tags.by_lower


# --------------------------------------------------------------------------- #
# Delete flow (M1 PR6, FR-LIB-10..12)
# --------------------------------------------------------------------------- #

# The fakes for tags/genres are independent of FakeFilmRepository, so they do
# not simulate the real ``film_tags``/``film_genres`` FK cascade a film
# deletion triggers — that cascade, and the orphan sweep it enables, is a
# repository/database behaviour verified against real Postgres in
# ``test_films_api.py``. What the service *owns* and what these tests check:
# the film (and, in this repository, its titles) is gone, both label kinds'
# ``delete_orphans`` are reached exactly once, and it all shares one commit.


def test_delete_removes_the_film_and_its_titles_and_sweeps_both_label_kinds() -> None:
    service, repository, tags, genres, _ = make_service_with_genres()
    created = service.create(payload())
    commits_before = repository.commits

    service.delete(created.id)

    assert created.id not in repository.films
    assert repository.list_titles(created.id) == []
    assert repository.commits == commits_before + 1
    assert tags.orphan_sweeps == 1
    assert genres.orphan_sweeps == 1


def test_delete_unknown_film_id_maps_to_not_found_and_changes_nothing() -> None:
    service, repository, tags, genres, _ = make_service_with_genres()
    commits_before = repository.commits

    with pytest.raises(FilmNotFoundError) as caught:
        service.delete(uuid.uuid4())

    assert caught.value.code == "NOT_FOUND"
    assert caught.value.status_code == 404
    assert repository.commits == commits_before
    assert tags.orphan_sweeps == 0
    assert genres.orphan_sweeps == 0
