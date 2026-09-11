"""End-to-end film-flow tests against real Postgres (M1 PR4/PR5/PR6/PR7 — §9, §5.4).

The full stack — router → service → repositories → Postgres — through
``TestClient`` over the PR2 harness session: the atomic create (FR-LIB-01..03),
the duplicate block and probe (FR-LIB-05), the §7.3 detail read with its
computed average (FR-RAT-05/06/09), the edit (FR-LIB-06..09), the cascading
delete (FR-LIB-10..12), the standalone rating lifecycle and the
last-rating-deletes-the-film rule (FR-RAT-01..08), and the envelope contract
of every error path (NFR-MAINT-03).

The overridden session dependency rolls back after each request, mirroring
production's ``get_session`` close semantics: a request that failed leaves
nothing behind (the atomicity acceptance check), while committed work — sealed
inside the harness' outer transaction — survives for the test to inspect.
"""

import uuid
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.db import get_session
from app.films.models import Film, Title
from app.genres.models import Genre
from app.genres.service import GenreService
from app.main import create_app
from app.ratings.models import RatingEntry
from app.tags.models import FilmTag, Tag

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _client_over(db_session: Session) -> TestClient:
    """The real app with the request session swapped for the harness one.

    The ``finally: rollback()`` mirrors what closing the request-scoped
    session does in production: uncommitted work from a failed request is
    discarded; work the service committed is unaffected.
    """
    app = create_app()

    def override() -> Iterator[Session]:
        try:
            yield db_session
        finally:
            db_session.rollback()

    app.dependency_overrides[get_session] = override
    return TestClient(app)


def _payload(**overrides: object) -> dict[str, object]:
    """A valid "log a watched film" body (FR-LIB-01..03), overridable per test."""
    body: dict[str, object] = {
        "titles": [
            {"value": "Heat", "is_primary": True},
            {"value": "Fuego", "is_original": True},
        ],
        "release_year": 1995,
        "director": "Michael Mann",
        "genre": ["Crime", "Thriller"],
        "tags": ["heist", "la"],
        "poster_image": "https://example.org/heat.jpg",
        "first_rating": {"value": 4.5, "watch_date": "1995-12-15"},
    }
    body.update(overrides)
    return body


def _count(db_session: Session, model: type[Film | Title | RatingEntry | Tag | Genre]) -> int:
    count = db_session.scalar(select(func.count()).select_from(model))
    assert count is not None
    return count


def _error_code(body: object) -> str:
    envelope = cast(dict[str, dict[str, str]], body)
    assert set(envelope) == {"error"} and set(envelope["error"]) == {"code", "message"}
    return envelope["error"]["code"]


# --------------------------------------------------------------------------- #
# The create flow (FR-LIB-01..05)
# --------------------------------------------------------------------------- #


def test_create_returns_201_with_the_full_projection_and_no_natural_key(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    response = client.post("/api/v1/films", json=_payload())

    assert response.status_code == 201
    body = cast(dict[str, object], response.json())
    # The exact §7.3 projection — natural_key deliberately absent (FR-LIB-04).
    assert set(body) == {
        "id",
        "titles",
        "release_year",
        "director",
        "genre",
        "tags",
        "poster_image",
        "is_favorite",
        "delay_days",
        "rating_history",
        "average_rating",
        "created_at",
        "updated_at",
    }
    assert body["genre"] == ["Crime", "Thriller"]
    assert body["tags"] == ["heist", "la"]
    assert body["average_rating"] == 4.5
    assert body["is_favorite"] is False and body["delay_days"] == 0  # FR-LIB-02
    assert body["created_at"] is not None and body["updated_at"] is not None

    titles = cast(list[dict[str, object]], body["titles"])
    assert [title["value"] for title in titles] == ["Heat", "Fuego"]  # primary first

    # Everything persisted in one unit of work (FR-LIB-03).
    film_id = uuid.UUID(cast(str, body["id"]))
    film = db_session.get(Film, film_id)
    assert film is not None
    assert film.natural_key == "heat|1995|michael mann"
    assert _count(db_session, Title) == 2
    assert _count(db_session, RatingEntry) == 1
    assert db_session.scalars(select(FilmTag).where(FilmTag.film_id == film_id)).all() != []

    # The detail read serves the same projection (§7.3).
    assert client.get(f"/api/v1/films/{film_id}").json() == body


def test_each_validation_failure_yields_the_validation_error_envelope(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    payload_without_rating = _payload()
    del payload_without_rating["first_rating"]
    bad_bodies: list[dict[str, object]] = [
        payload_without_rating,  # FR-LIB-03: first rating is mandatory
        _payload(tags=[]),  # ≥1 tag
        _payload(genre=[]),  # ≥1 genre
        _payload(
            titles=[
                {"value": "Heat", "is_primary": True},
                {"value": "Fuego", "is_primary": True},
            ]
        ),  # two primaries
        _payload(first_rating={"value": 4.5, "watch_date": "2999-01-01"}),  # future date
        _payload(first_rating={"value": 4.3, "watch_date": "1995-12-15"}),  # off-step value
        _payload(release_year="1995"),  # lossy-typed field (§5.7)
        _payload(natural_key="heat|1995|michael mann"),  # unknown/system field
        _payload(is_favorite=True),  # not accepted at create (FR-LIB-02)
        _payload(poster_image="not a url"),  # FR-LIB-14
    ]
    for body in bad_bodies:
        response = client.post("/api/v1/films", json=body)
        assert response.status_code == 422, body
        assert _error_code(response.json()) == "VALIDATION_ERROR"
    assert _count(db_session, Film) == 0


def test_duplicate_create_is_blocked_with_duplicate_film_identifying_the_existing(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    first = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())

    # Case- and whitespace-different on every key part (FR-LIB-05).
    response = client.post(
        "/api/v1/films",
        json=_payload(
            titles=[{"value": "  HEAT ", "is_primary": True}],
            director="michael mann ",
            tags=["other"],
            genre=["Other"],
        ),
    )
    assert response.status_code == 409
    body = cast(dict[str, dict[str, str]], response.json())
    assert body["error"]["code"] == "DUPLICATE_FILM"
    # The message identifies the existing film so the client can offer to open it.
    assert str(first["id"]) in body["error"]["message"]
    assert "Heat" in body["error"]["message"]
    assert _count(db_session, Film) == 1


def test_duplicate_check_probe_answers_without_creating_anything(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())

    hit = client.post(
        "/api/v1/films/duplicate-check",
        json={"primary_title": " HEAT", "release_year": 1995, "director": "michael MANN "},
    )
    assert hit.status_code == 200
    hit_body = cast(dict[str, object], hit.json())
    assert hit_body["duplicate"] is True
    assert cast(dict[str, object], hit_body["film"])["id"] == created["id"]

    miss = client.post(
        "/api/v1/films/duplicate-check",
        json={"primary_title": "Heat", "release_year": 1996, "director": "Michael Mann"},
    )
    assert cast(dict[str, object], miss.json()) == {"duplicate": False, "film": None}
    assert _count(db_session, Film) == 1  # the probe never writes


def test_client_minted_id_is_honoured_and_a_collision_is_a_validation_error(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    minted = str(uuid.uuid4())
    created = client.post("/api/v1/films", json=_payload(id=minted))
    assert created.status_code == 201
    assert cast(dict[str, object], created.json())["id"] == minted

    collision = client.post(
        "/api/v1/films",
        json=_payload(id=minted, titles=[{"value": "Collateral", "is_primary": True}]),
    )
    assert collision.status_code == 422
    assert _error_code(collision.json()) == "VALIDATION_ERROR"
    assert _count(db_session, Film) == 1


def test_labels_are_shared_across_films_case_insensitively(db_session: Session) -> None:
    # FR-TAG-01/02 through the film payload: the second film reuses the first's
    # labels however cased — one row per label, two links.
    client = _client_over(db_session)
    assert client.post("/api/v1/films", json=_payload()).status_code == 201
    second = client.post(
        "/api/v1/films",
        json=_payload(
            titles=[{"value": "Collateral", "is_primary": True}],
            release_year=2004,
            tags=["HEIST"],
            genre=["crime"],
        ),
    )
    assert second.status_code == 201
    assert db_session.scalars(select(Tag).where(func.lower(Tag.name) == "heist")).one()
    assert db_session.scalars(select(Genre).where(func.lower(Genre.name) == "crime")).one()
    assert _count(db_session, Film) == 2


def test_a_failure_mid_create_leaves_no_partial_rows(db_session: Session) -> None:
    # The 51-char tag passes the create schema but fails the tag service's
    # REQ §4.3 rule *after* the film, titles, and rating joined the unit of
    # work — the whole create must roll back (FR-LIB-03, NFR-INT-02).
    client = _client_over(db_session)
    response = client.post("/api/v1/films", json=_payload(tags=["x" * 51]))

    assert response.status_code == 422
    assert _error_code(response.json()) == "VALIDATION_ERROR"
    for model in (Film, Title, RatingEntry, Tag, Genre):
        assert _count(db_session, model) == 0, model.__name__


# --------------------------------------------------------------------------- #
# The detail read (§7.3, FR-RAT-05/06/09)
# --------------------------------------------------------------------------- #


def test_detail_orders_history_desc_and_computes_the_rounded_average(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = uuid.UUID(cast(str, created["id"]))

    # A second, earlier watch recorded directly (the rating endpoints are PR7).
    db_session.add(
        RatingEntry(film_id=film_id, value=Decimal("4.0"), watch_date=date(1995, 12, 10))
    )
    db_session.flush()

    body = cast(dict[str, object], client.get(f"/api/v1/films/{film_id}").json())
    history = cast(list[dict[str, object]], body["rating_history"])
    assert [entry["watch_date"] for entry in history] == ["1995-12-15", "1995-12-10"]
    assert [entry["value"] for entry in history] == [4.5, 4.0]
    assert set(history[0]) == {"id", "value", "watch_date", "created_at"}
    # (4.5 + 4.0) / 2 = 4.25 → half-up to one decimal (FR-RAT-09), fresh on
    # this read — never stored (NFR-INT-01).
    assert body["average_rating"] == 4.3


def test_unknown_and_malformed_film_ids_map_to_the_envelope(db_session: Session) -> None:
    client = _client_over(db_session)
    missing = client.get(f"/api/v1/films/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert _error_code(missing.json()) == "NOT_FOUND"

    malformed = client.get("/api/v1/films/not-a-uuid")
    assert malformed.status_code == 422
    assert _error_code(malformed.json()) == "VALIDATION_ERROR"


# --------------------------------------------------------------------------- #
# The edit flow (FR-LIB-06..09)
# --------------------------------------------------------------------------- #


def _timestamp(value: object) -> datetime:
    assert isinstance(value, str)
    return datetime.fromisoformat(value)


def test_edit_updates_fields_and_bumps_updated_at_never_created_at(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = created["id"]

    response = client.patch(
        f"/api/v1/films/{film_id}",
        json={
            "release_year": 1996,
            "director": "Someone Else",
            "is_favorite": True,
            "delay_days": 7,
        },
    )
    assert response.status_code == 200
    body = cast(dict[str, object], response.json())
    assert body["release_year"] == 1996
    assert body["director"] == "Someone Else"
    assert body["is_favorite"] is True
    assert body["delay_days"] == 7
    assert body["created_at"] == created["created_at"]
    assert _timestamp(body["updated_at"]) > _timestamp(created["updated_at"])
    assert "natural_key" not in body

    # Persisted — the detail read agrees.
    assert client.get(f"/api/v1/films/{film_id}").json() == body


def test_edit_empty_body_is_a_no_op(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = created["id"]

    response = client.patch(f"/api/v1/films/{film_id}", json={})
    assert response.status_code == 200
    assert response.json() == created


def test_edit_recomputes_natural_key_and_blocks_a_collision_leaving_the_film_unchanged(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    heat = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    collateral = cast(
        dict[str, object],
        client.post(
            "/api/v1/films",
            json=_payload(
                titles=[{"value": "Collateral", "is_primary": True}],
                release_year=2004,
                tags=["other"],
                genre=["Other"],
            ),
        ).json(),
    )

    response = client.patch(
        f"/api/v1/films/{collateral['id']}",
        json={
            "titles": [{"value": "  HEAT ", "is_primary": True}],
            "release_year": 1995,
            "director": "michael mann ",
        },
    )
    assert response.status_code == 409
    body = cast(dict[str, dict[str, str]], response.json())
    assert body["error"]["code"] == "DUPLICATE_FILM"
    assert str(heat["id"]) in body["error"]["message"]

    # Unapplied (FR-LIB-09): re-reading shows the film exactly as it was.
    assert client.get(f"/api/v1/films/{collateral['id']}").json() == collateral

    film_id = uuid.UUID(cast(str, collateral["id"]))
    film = db_session.get(Film, film_id)
    assert film is not None
    assert film.natural_key == "collateral|2004|michael mann"


def test_edit_titles_are_replaced_and_the_title_rules_still_hold(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = uuid.UUID(cast(str, created["id"]))

    two_primaries = client.patch(
        f"/api/v1/films/{film_id}",
        json={
            "titles": [
                {"value": "Heat", "is_primary": True},
                {"value": "Fuego", "is_primary": True},
            ]
        },
    )
    assert two_primaries.status_code == 422
    assert _error_code(two_primaries.json()) == "VALIDATION_ERROR"
    assert _count(db_session, Title) == 2  # rejected: the original titles survive

    replaced = client.patch(
        f"/api/v1/films/{film_id}",
        json={"titles": [{"value": "Collateral", "is_primary": True}]},
    )
    assert replaced.status_code == 200
    body = cast(dict[str, object], replaced.json())
    titles = cast(list[dict[str, object]], body["titles"])
    assert [title["value"] for title in titles] == ["Collateral"]
    assert _count(db_session, Title) == 1  # the old two titles are gone, not just unlinked


def test_edit_poster_can_be_set_replaced_and_removed(db_session: Session) -> None:
    client = _client_over(db_session)
    body = _payload()
    del body["poster_image"]
    created = cast(dict[str, object], client.post("/api/v1/films", json=body).json())
    film_id = created["id"]
    assert created["poster_image"] is None

    set_ = client.patch(
        f"/api/v1/films/{film_id}", json={"poster_image": "https://example.org/a.jpg"}
    )
    assert cast(dict[str, object], set_.json())["poster_image"] == "https://example.org/a.jpg"

    invalid = client.patch(f"/api/v1/films/{film_id}", json={"poster_image": "not a url"})
    assert invalid.status_code == 422
    assert _error_code(invalid.json()) == "VALIDATION_ERROR"

    removed = client.patch(f"/api/v1/films/{film_id}", json={"poster_image": None})
    assert removed.status_code == 200
    assert cast(dict[str, object], removed.json())["poster_image"] is None

    unrelated_edit = client.patch(f"/api/v1/films/{film_id}", json={"is_favorite": True})
    assert cast(dict[str, object], unrelated_edit.json())["poster_image"] is None


def test_edit_rejects_immutable_and_unknown_fields(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = created["id"]

    for override in (
        {"id": str(uuid.uuid4())},
        {"created_at": "2020-01-01T00:00:00Z"},
        {"natural_key": "heat|1995|michael mann"},
        {"average_rating": 1.0},
    ):
        response = client.patch(f"/api/v1/films/{film_id}", json=override)
        assert response.status_code == 422, override
        assert _error_code(response.json()) == "VALIDATION_ERROR"

    # None of the rejected attempts touched the film.
    assert client.get(f"/api/v1/films/{film_id}").json() == created


def test_edit_reassigns_labels_deleting_orphans_but_sparing_shared_ones(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    solo = cast(
        dict[str, object],
        client.post("/api/v1/films", json=_payload(tags=["heist"], genre=["Crime"])).json(),
    )
    client.post(
        "/api/v1/films",
        json=_payload(
            titles=[{"value": "Collateral", "is_primary": True}],
            release_year=2004,
            tags=["heist"],
            genre=["Crime"],
        ),
    )

    response = client.patch(
        f"/api/v1/films/{solo['id']}", json={"tags": ["la"], "genre": ["Thriller"]}
    )
    assert response.status_code == 200
    body = cast(dict[str, object], response.json())
    assert body["tags"] == ["la"]
    assert body["genre"] == ["Thriller"]

    # "heist"/"Crime" survive — still linked to the other film.
    assert db_session.scalars(select(Tag).where(func.lower(Tag.name) == "heist")).one()
    assert db_session.scalars(select(Genre).where(func.lower(Genre.name) == "crime")).one()


def test_edit_removing_a_films_only_label_link_deletes_the_orphan(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(
        dict[str, object],
        client.post("/api/v1/films", json=_payload(tags=["heist"], genre=["Crime"])).json(),
    )

    response = client.patch(
        f"/api/v1/films/{created['id']}", json={"tags": ["la"], "genre": ["Thriller"]}
    )
    assert response.status_code == 200

    assert (
        db_session.scalars(select(Tag).where(func.lower(Tag.name) == "heist")).one_or_none() is None
    )
    assert (
        db_session.scalars(select(Genre).where(func.lower(Genre.name) == "crime")).one_or_none()
        is None
    )


def test_edit_unknown_film_id_maps_to_the_not_found_envelope(db_session: Session) -> None:
    client = _client_over(db_session)
    response = client.patch(f"/api/v1/films/{uuid.uuid4()}", json={"is_favorite": True})
    assert response.status_code == 404
    assert _error_code(response.json()) == "NOT_FOUND"


# --------------------------------------------------------------------------- #
# The delete flow (M1 PR6, FR-LIB-10..12, NFR-INT-02)
# --------------------------------------------------------------------------- #


def test_delete_cascades_everything_and_spares_labels_shared_with_other_films(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    solo = cast(
        dict[str, object],
        client.post("/api/v1/films", json=_payload(tags=["heist"], genre=["Crime"])).json(),
    )
    film_id = uuid.UUID(cast(str, solo["id"]))
    other = cast(
        dict[str, object],
        client.post(
            "/api/v1/films",
            json=_payload(
                titles=[{"value": "Collateral", "is_primary": True}],
                release_year=2004,
                tags=["heist"],
                genre=["Crime"],
            ),
        ).json(),
    )

    response = client.delete(f"/api/v1/films/{film_id}")
    assert response.status_code == 204
    assert response.content == b""

    # The film, its title, and its rating are gone (PR1's ON DELETE CASCADE).
    assert db_session.get(Film, film_id) is None
    assert db_session.scalars(select(Title).where(Title.film_id == film_id)).all() == []
    assert db_session.scalars(select(RatingEntry).where(RatingEntry.film_id == film_id)).all() == []
    assert db_session.scalars(select(FilmTag).where(FilmTag.film_id == film_id)).all() == []

    # "heist"/"Crime" are solely this film's no longer — but the other film
    # still uses them, so they survive (FR-LIB-12/FR-TAG-04).
    assert db_session.scalars(select(Tag).where(func.lower(Tag.name) == "heist")).one()
    assert db_session.scalars(select(Genre).where(func.lower(Genre.name) == "crime")).one()
    assert client.get(f"/api/v1/films/{other['id']}").status_code == 200


def test_delete_removes_a_films_only_label_link_as_an_orphan(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(
        dict[str, object],
        client.post("/api/v1/films", json=_payload(tags=["heist"], genre=["Crime"])).json(),
    )

    response = client.delete(f"/api/v1/films/{created['id']}")
    assert response.status_code == 204

    assert (
        db_session.scalars(select(Tag).where(func.lower(Tag.name) == "heist")).one_or_none() is None
    )
    assert (
        db_session.scalars(select(Genre).where(func.lower(Genre.name) == "crime")).one_or_none()
        is None
    )


def test_a_failure_mid_delete_leaves_no_partial_rows(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # By the time the genre orphan sweep runs, the film delete and the tag
    # orphan sweep have already joined the same not-yet-committed unit of
    # work (NFR-INT-02) — an unexpected failure here must roll back all of
    # it, leaving the film, its rating, its title, and its labels untouched.
    client = _client_over(db_session)
    created = cast(
        dict[str, object],
        client.post("/api/v1/films", json=_payload(tags=["heist"], genre=["Crime"])).json(),
    )
    film_id = uuid.UUID(cast(str, created["id"]))

    def boom(self: GenreService) -> int:
        raise RuntimeError(
            "simulated failure after the film delete already joined the unit of work"
        )

    monkeypatch.setattr(GenreService, "delete_orphans", boom)

    with pytest.raises(RuntimeError):
        client.delete(f"/api/v1/films/{film_id}")

    assert db_session.get(Film, film_id) is not None
    for model in (Title, RatingEntry, FilmTag):
        assert db_session.scalars(select(model).where(model.film_id == film_id)).all() != []
    assert db_session.scalars(select(Tag).where(func.lower(Tag.name) == "heist")).one()
    assert db_session.scalars(select(Genre).where(func.lower(Genre.name) == "crime")).one()


def test_deleting_an_unknown_or_already_deleted_film_yields_not_found(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    missing = client.delete(f"/api/v1/films/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert _error_code(missing.json()) == "NOT_FOUND"

    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = created["id"]
    assert client.delete(f"/api/v1/films/{film_id}").status_code == 204

    repeat = client.delete(f"/api/v1/films/{film_id}")
    assert repeat.status_code == 404
    assert _error_code(repeat.json()) == "NOT_FOUND"


# --------------------------------------------------------------------------- #
# The standalone rating lifecycle (M1 PR7, FR-RAT-01..08)
# --------------------------------------------------------------------------- #


def test_add_rating_returns_201_and_the_detail_read_reflects_the_updated_average(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = created["id"]

    response = client.post(
        f"/api/v1/films/{film_id}/ratings",
        json={"value": 3.5, "watch_date": "1995-12-20"},
    )
    assert response.status_code == 201
    added = cast(dict[str, object], response.json())
    assert set(added) == {"id", "value", "watch_date", "created_at"}
    assert added["value"] == 3.5

    detail = cast(dict[str, object], client.get(f"/api/v1/films/{film_id}").json())
    history = cast(list[dict[str, object]], detail["rating_history"])
    # Most recent watch_date first (FR-RAT-05/06); the original 4.5@12-15 vs
    # the new 3.5@12-20 — the later watch_date leads.
    assert [entry["watch_date"] for entry in history] == ["1995-12-20", "1995-12-15"]
    # (4.5 + 3.5) / 2 = 4.0 (FR-RAT-09/10), fresh on this read (NFR-INT-01).
    assert detail["average_rating"] == 4.0
    assert _count(db_session, RatingEntry) == 2


def test_add_rating_future_watch_date_yields_the_future_watch_date_envelope(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())

    response = client.post(
        f"/api/v1/films/{created['id']}/ratings",
        json={"value": 3.5, "watch_date": "2999-01-01"},
    )
    assert response.status_code == 422
    assert _error_code(response.json()) == "FUTURE_WATCH_DATE"
    assert _count(db_session, RatingEntry) == 1  # only the mandatory first rating


def test_add_rating_off_step_value_yields_validation_error(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())

    response = client.post(
        f"/api/v1/films/{created['id']}/ratings",
        json={"value": 3.3, "watch_date": "1995-12-20"},
    )
    assert response.status_code == 422
    assert _error_code(response.json()) == "VALIDATION_ERROR"
    assert _count(db_session, RatingEntry) == 1


def test_two_ratings_on_the_same_watch_date_coexist(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = created["id"]

    # FR-RAT-04: same-day repeats are allowed — the mandatory first rating was
    # already recorded on 1995-12-15.
    response = client.post(
        f"/api/v1/films/{film_id}/ratings",
        json={"value": 5.0, "watch_date": "1995-12-15"},
    )
    assert response.status_code == 201
    assert _count(db_session, RatingEntry) == 2

    history = cast(
        list[dict[str, object]],
        cast(dict[str, object], client.get(f"/api/v1/films/{film_id}").json())["rating_history"],
    )
    assert len(history) == 2
    assert {entry["watch_date"] for entry in history} == {"1995-12-15"}


def test_add_rating_unknown_film_id_yields_not_found(db_session: Session) -> None:
    client = _client_over(db_session)
    response = client.post(
        f"/api/v1/films/{uuid.uuid4()}/ratings",
        json={"value": 3.5, "watch_date": "1995-12-20"},
    )
    assert response.status_code == 404
    assert _error_code(response.json()) == "NOT_FOUND"


def test_delete_rating_removes_only_that_entry_when_others_remain(db_session: Session) -> None:
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = created["id"]
    second = cast(
        dict[str, object],
        client.post(
            f"/api/v1/films/{film_id}/ratings",
            json={"value": 3.0, "watch_date": "1995-12-20"},
        ).json(),
    )

    response = client.delete(f"/api/v1/ratings/{second['id']}")
    assert response.status_code == 200
    body = cast(dict[str, object], response.json())
    assert body == {"rating_id": second["id"], "film_id": film_id, "film_deleted": False}

    assert _count(db_session, RatingEntry) == 1
    assert client.get(f"/api/v1/films/{film_id}").status_code == 200  # the film survives


def test_delete_rating_deletes_the_whole_film_when_it_was_the_last_one(
    db_session: Session,
) -> None:
    client = _client_over(db_session)
    created = cast(
        dict[str, object],
        client.post("/api/v1/films", json=_payload(tags=["heist"], genre=["Crime"])).json(),
    )
    film_id = created["id"]
    history = cast(list[dict[str, object]], created["rating_history"])
    (only_rating,) = history

    response = client.delete(f"/api/v1/ratings/{only_rating['id']}")
    assert response.status_code == 200
    body = cast(dict[str, object], response.json())
    assert body == {"rating_id": only_rating["id"], "film_id": film_id, "film_deleted": True}

    # The film, its rating, and its now-orphaned labels are all gone —
    # PR6's cascade + orphan-cleanup flow, reused verbatim (FR-RAT-07).
    assert client.get(f"/api/v1/films/{film_id}").status_code == 404
    assert _count(db_session, RatingEntry) == 0
    assert (
        db_session.scalars(select(Tag).where(func.lower(Tag.name) == "heist")).one_or_none() is None
    )
    assert (
        db_session.scalars(select(Genre).where(func.lower(Genre.name) == "crime")).one_or_none()
        is None
    )


def test_delete_rating_unknown_id_yields_not_found(db_session: Session) -> None:
    client = _client_over(db_session)
    response = client.delete(f"/api/v1/ratings/{uuid.uuid4()}")
    assert response.status_code == 404
    assert _error_code(response.json()) == "NOT_FOUND"


def test_no_patch_or_put_route_exists_for_ratings(db_session: Session) -> None:
    # FR-RAT-08: corrections are delete-then-recreate, never an edit.
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    history = cast(list[dict[str, object]], created["rating_history"])
    (rating,) = history

    assert client.patch(f"/api/v1/ratings/{rating['id']}", json={"value": 5.0}).status_code == 405
    assert client.put(f"/api/v1/ratings/{rating['id']}", json={"value": 5.0}).status_code == 405


def test_fixing_a_films_only_rating_requires_add_then_delete_not_delete_then_add(
    db_session: Session,
) -> None:
    # FR-RAT-08: there is no rating-edit endpoint, so "fixing" a film's only
    # rating means adding the corrected entry *first*, then deleting the
    # wrong one — deleting the sole rating first is destructive, since it
    # triggers the last-rating-deletes-the-film rule (FR-RAT-07) before the
    # correction ever lands.
    client = _client_over(db_session)
    created = cast(
        dict[str, object],
        client.post(
            "/api/v1/films", json=_payload(first_rating={"value": 3.0, "watch_date": "1995-12-15"})
        ).json(),
    )
    film_id = created["id"]
    history = cast(list[dict[str, object]], created["rating_history"])
    (wrong_rating,) = history

    # The safe order: add the correction, then delete the mistake.
    corrected = cast(
        dict[str, object],
        client.post(
            f"/api/v1/films/{film_id}/ratings",
            json={"value": 4.5, "watch_date": "1995-12-15"},
        ).json(),
    )
    delete_response = client.delete(f"/api/v1/ratings/{wrong_rating['id']}")
    assert delete_response.status_code == 200
    assert cast(dict[str, object], delete_response.json())["film_deleted"] is False

    detail = cast(dict[str, object], client.get(f"/api/v1/films/{film_id}").json())
    remaining = cast(list[dict[str, object]], detail["rating_history"])
    assert [entry["id"] for entry in remaining] == [corrected["id"]]
    assert detail["average_rating"] == 4.5


def test_deleting_a_films_sole_rating_first_is_destructive(db_session: Session) -> None:
    # The other ordering: deleting the (only) rating before adding a
    # replacement destroys the film — demonstrated as a warning against it.
    client = _client_over(db_session)
    created = cast(dict[str, object], client.post("/api/v1/films", json=_payload()).json())
    film_id = created["id"]
    history = cast(list[dict[str, object]], created["rating_history"])
    (only_rating,) = history

    response = client.delete(f"/api/v1/ratings/{only_rating['id']}")
    assert cast(dict[str, object], response.json())["film_deleted"] is True
    assert client.get(f"/api/v1/films/{film_id}").status_code == 404
