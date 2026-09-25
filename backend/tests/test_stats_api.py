"""``GET /stats`` end to end, offline: the service is stubbed with a real :class:`Stats`."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.stats.algorithm import Stats, Watch, compute
from app.stats.dependencies import get_stats_service

FILM = uuid.uuid4()


def _client(stats: Stats) -> TestClient:
    app = create_app()

    class StubService:
        def stats(self, today: date) -> Stats:
            return stats

    app.dependency_overrides[get_stats_service] = StubService
    return TestClient(app)


def test_the_payload_carries_total_and_flattened_years() -> None:
    watch = Watch(
        FILM, "Heat", 1995, "Michael Mann", 170, ("Crime",), date(2026, 3, 1), Decimal("4.5")
    )

    body = _client(compute([watch], date(2026, 9, 25))).get("/api/v1/stats").json()

    assert body["total"]["films_released_that_year"] is None
    assert body["total"]["average_rating"] == 4.5
    assert body["total"]["top_films"] == [
        {"film_id": str(FILM), "title": "Heat", "watches": 1, "average_rating": 4.5, "score": 4.5}
    ]
    assert body["total"]["top_directors"] == [
        {"name": "Michael Mann", "watches": 1, "average_rating": 4.5, "score": 4.5}
    ]
    assert body["total"]["top_genres"] == [
        {"name": "Crime", "watches": 1, "average_rating": 4.5, "score": 4.5}
    ]
    [year] = body["years"]
    assert year["year"] == 2026
    assert year["watches"] == 1
    assert year["buckets"][2] == {"label": "3", "count": 1}


def test_an_empty_library_is_a_normal_answer() -> None:
    response = _client(compute([], date(2026, 9, 25))).get("/api/v1/stats")

    assert response.status_code == 200
    assert response.json()["years"] == []
