"""The letterboxd routes end to end, with the service stubbed (offline)."""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.films.service import FilmNotFoundError
from app.letterboxd.dependencies import get_letterboxd_service
from app.letterboxd.errors import (
    EntryNotFoundError,
    EntryResolvedError,
    LetterboxdDisabledError,
    LetterboxdUnavailableError,
)
from app.letterboxd.schemas import LetterboxdEntryRead, SuggestedFilmRead
from app.main import create_app

ENTRY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
FILM_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class StubService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, object]] = []

    def _maybe_fail(self) -> None:
        if self.error is not None:
            raise self.error

    def list_open(self) -> list[LetterboxdEntryRead]:
        return [
            LetterboxdEntryRead(
                id=ENTRY_ID,
                film_title="Heat",
                film_year=1995,
                film_url="https://letterboxd.com/film/heat/",
                watched_date=date(2026, 9, 20),
                rating=None,
                rewatch=True,
                suggested_film=SuggestedFilmRead(id=FILM_ID, title="Heat"),
            )
        ]

    def assign(self, entry_id: uuid.UUID, film_id: uuid.UUID) -> None:
        self._maybe_fail()
        self.calls.append(("assign", (entry_id, film_id)))

    def dismiss(self, entry_id: uuid.UUID) -> None:
        self._maybe_fail()
        self.calls.append(("dismiss", entry_id))

    def sync(self) -> int:
        self._maybe_fail()
        return 3


def _client(service: StubService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_letterboxd_service] = lambda: service
    return TestClient(app)


def test_lists_open_entries() -> None:
    response = _client(StubService()).get("/api/v1/letterboxd/entries")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(ENTRY_ID),
            "film_title": "Heat",
            "film_year": 1995,
            "film_url": "https://letterboxd.com/film/heat/",
            "watched_date": "2026-09-20",
            "rating": None,
            "rewatch": True,
            "suggested_film": {"id": str(FILM_ID), "title": "Heat"},
        }
    ]


def test_assign() -> None:
    service = StubService()
    response = _client(service).post(
        f"/api/v1/letterboxd/entries/{ENTRY_ID}/assign", json={"film_id": str(FILM_ID)}
    )

    assert response.status_code == 204
    assert service.calls == [("assign", (ENTRY_ID, FILM_ID))]


def test_dismiss() -> None:
    service = StubService()
    response = _client(service).post(f"/api/v1/letterboxd/entries/{ENTRY_ID}/dismiss")

    assert response.status_code == 204
    assert service.calls == [("dismiss", ENTRY_ID)]


def test_sync_reports_the_queued_count() -> None:
    response = _client(StubService()).post("/api/v1/letterboxd/sync")

    assert response.status_code == 200
    assert response.json() == {"queued": 3}


def test_error_codes() -> None:
    cases: list[tuple[Exception, str, str, int, str]] = [
        (EntryNotFoundError(ENTRY_ID), "post", f"/entries/{ENTRY_ID}/dismiss", 404, "NOT_FOUND"),
        (
            EntryResolvedError(ENTRY_ID),
            "post",
            f"/entries/{ENTRY_ID}/dismiss",
            409,
            "ENTRY_RESOLVED",
        ),
        (FilmNotFoundError(FILM_ID), "post", f"/entries/{ENTRY_ID}/assign", 404, "NOT_FOUND"),
        (LetterboxdDisabledError(), "post", "/sync", 409, "LETTERBOXD_DISABLED"),
        (LetterboxdUnavailableError(), "post", "/sync", 502, "LETTERBOXD_UNAVAILABLE"),
    ]
    for error, method, path, status, code in cases:
        client = _client(StubService(error))
        body = {"film_id": str(FILM_ID)} if path.endswith("assign") else None
        response = client.request(method, f"/api/v1/letterboxd{path}", json=body)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code), path


def test_assign_rejects_a_malformed_film_id() -> None:
    response = _client(StubService()).post(
        f"/api/v1/letterboxd/entries/{ENTRY_ID}/assign", json={"film_id": "nope"}
    )

    assert response.status_code == 422
