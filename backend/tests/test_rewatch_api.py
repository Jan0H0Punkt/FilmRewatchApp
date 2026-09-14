"""``GET /rewatch-suggestions`` end to end (DESIGN §5.3, FR-RW-03/04/06).

Offline: the service dependency is overridden with a stub, so the route's
serialisation and ordering are tested without a database.
"""

import uuid
from collections.abc import Sequence

from fastapi.testclient import TestClient

from app.core.db import utc_now
from app.main import create_app
from app.rewatch.dependencies import get_rewatch_service
from app.rewatch.models import RewatchSuggestion


def _client(rows: Sequence[RewatchSuggestion]) -> TestClient:
    app = create_app()

    class StubService:
        def list_suggestions(self) -> Sequence[RewatchSuggestion]:
            return rows

    app.dependency_overrides[get_rewatch_service] = StubService
    return TestClient(app)


def _row(days: int, position: int) -> RewatchSuggestion:
    return RewatchSuggestion(
        film_id=uuid.uuid4(),
        days_until_next_rewatch=days,
        position=position,
        computed_at=utc_now(),
    )


def test_an_empty_projection_serves_an_empty_list() -> None:
    # FR-RW-06: the empty state is the view's job, not an error here.
    response = _client([]).get("/api/v1/rewatch-suggestions")

    assert response.status_code == 200
    assert response.json() == []


def test_the_response_carries_only_the_two_contract_fields() -> None:
    row = _row(-12, 0)

    response = _client([row]).get("/api/v1/rewatch-suggestions")

    assert response.json() == [{"film_id": str(row.film_id), "days_until_next_rewatch": -12}]


def test_the_stored_order_reaches_the_wire_unchanged() -> None:
    # FR-RW-04: the API re-sorts nothing; it serves what the run stored.
    rows = [_row(-40, 0), _row(-1, 1), _row(0, 2)]

    payload = _client(rows).get("/api/v1/rewatch-suggestions").json()

    assert [item["days_until_next_rewatch"] for item in payload] == [-40, -1, 0]
    assert [item["film_id"] for item in payload] == [str(row.film_id) for row in rows]
