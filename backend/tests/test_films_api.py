"""End-to-end film-flow tests against real Postgres (M1 PR4 — §9, §5.4).

The full stack — router → service → repositories → Postgres — through
``TestClient`` over the PR2 harness session: the atomic create (FR-LIB-01..03),
the duplicate block and probe (FR-LIB-05), the §7.3 detail read with its
computed average (FR-RAT-05/06/09), and the envelope contract of every error
path (NFR-MAINT-03).

The overridden session dependency rolls back after each request, mirroring
production's ``get_session`` close semantics: a request that failed leaves
nothing behind (the atomicity acceptance check), while committed work — sealed
inside the harness' outer transaction — survives for the test to inspect.
"""

import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.db import get_session
from app.films.models import Film, Title
from app.genres.models import Genre
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
