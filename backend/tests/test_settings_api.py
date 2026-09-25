"""``GET``/``PUT /settings`` end to end (DESIGN §5.3, FR-RW-08).

Offline: the service dependency is overridden with a stub, so the route's
serialisation and validation are tested without a database.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings.dependencies import get_settings_service
from app.settings.models import Settings


def _client(initial: int | None = None) -> TestClient:
    app = create_app()

    class StubService:
        def __init__(self) -> None:
            self.row = Settings(id=1, rewatch_share=initial, updated_at=datetime.now(UTC))

        def get(self) -> Settings:
            return self.row

        def update(self, rewatch_share: int | None) -> Settings:
            self.row.rewatch_share = rewatch_share
            return self.row

    app.dependency_overrides[get_settings_service] = StubService
    return TestClient(app)


def test_get_returns_the_stored_value() -> None:
    response = _client(initial=40).get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json() == {"rewatch_share": 40}


def test_get_reports_off_as_null() -> None:
    response = _client(initial=None).get("/api/v1/settings")

    assert response.json() == {"rewatch_share": None}


def test_put_replaces_the_stored_value() -> None:
    response = _client(initial=10).put("/api/v1/settings", json={"rewatch_share": 60})

    assert response.status_code == 200
    assert response.json() == {"rewatch_share": 60}


def test_put_can_turn_the_share_off() -> None:
    response = _client(initial=60).put("/api/v1/settings", json={"rewatch_share": None})

    assert response.json() == {"rewatch_share": None}


@pytest.mark.parametrize("value", [55, 110, -10])
def test_put_rejects_an_invalid_share(value: int) -> None:
    response = _client().put("/api/v1/settings", json={"rewatch_share": value})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
