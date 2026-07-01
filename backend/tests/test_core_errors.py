"""Tests for the single error envelope and its handlers (DESIGN §5.4, M0 PR5).

Proves that every error path is serialised to exactly
``{ "error": { "code", "message" } }`` (NFR-MAINT-03) and that the handlers are
wired on the real app so no route can emit another shape:

* a forced 404 on the real app → ``NOT_FOUND``;
* a 405 on the real app → the HTTP status name plus a preserved ``Allow`` header;
* a request-validation failure → ``VALIDATION_ERROR`` (422);
* an :class:`AppError` subclass → its own code / status / message;
* an unexpected crash → ``INTERNAL_ERROR`` (500) with nothing leaked.

Requests are driven through the ASGI app with Starlette's ``TestClient`` — the
path a real client takes — so the assertions reflect actual HTTP responses. The
validation / crash / domain-error cases need a route that exercises those paths;
M0 has none, so a tiny probe app registers the *same* handlers via
:func:`register_exception_handlers` and adds throwaway routes.
"""

from typing import cast

from fastapi import FastAPI, status
from starlette.testclient import TestClient

from app.core.errors import AppError, register_exception_handlers
from app.main import create_app


class _TeapotError(AppError):
    """Stand-in for an M1+ domain error, to prove subclasses render as-is."""

    code = "IM_A_TEAPOT"
    status_code = status.HTTP_418_IM_A_TEAPOT
    message = "No coffee here."


def _needs_int(count: int) -> dict[str, int]:
    """Route with a typed query param — a bad value triggers request validation."""
    return {"count": count}


def _raise_app_error() -> None:
    raise _TeapotError()


def _always_boom() -> None:
    raise RuntimeError("kaboom-secret — must never leak to the client")


def _build_probe_app() -> FastAPI:
    """A minimal app with the real handlers and routes that force each error."""
    app = FastAPI()
    register_exception_handlers(app)
    app.add_api_route("/needs-int", _needs_int, methods=["GET"])
    app.add_api_route("/teapot", _raise_app_error, methods=["GET"])
    app.add_api_route("/boom", _always_boom, methods=["GET"])
    return app


def _assert_envelope(payload: object, code: str) -> None:
    """Assert ``payload`` is exactly ``{ "error": { "code", "message" } }``."""
    assert isinstance(payload, dict)
    # ``response.json()`` is ``Any``; fix the JSON-object shape for the checker.
    body = cast(dict[str, object], payload)
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    detail = cast(dict[str, object], error)
    assert set(detail) == {"code", "message"}
    assert detail["code"] == code
    message = detail["message"]
    assert isinstance(message, str) and message


def test_forced_404_returns_not_found_envelope() -> None:
    # An unknown route on the real app: Starlette raises HTTPException(404),
    # which the handler reshapes into the envelope with the status-name code.
    client = TestClient(create_app())
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    _assert_envelope(response.json(), "NOT_FOUND")


def test_method_not_allowed_uses_status_name_and_keeps_allow_header() -> None:
    # /health is GET-only; POST yields a 405 whose Allow header must survive the
    # reshape, and whose code is derived from the HTTP status name.
    client = TestClient(create_app())
    response = client.post("/api/v1/health")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    _assert_envelope(response.json(), "METHOD_NOT_ALLOWED")
    assert "allow" in {key.lower() for key in response.headers}


def test_health_still_succeeds_with_handlers_registered() -> None:
    # Registering the handlers must not disturb the happy path.
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_validation_failure_returns_validation_envelope() -> None:
    client = TestClient(_build_probe_app())
    response = client.get("/needs-int", params={"count": "not-an-int"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    _assert_envelope(response.json(), "VALIDATION_ERROR")


def test_app_error_renders_its_code_status_and_message() -> None:
    client = TestClient(_build_probe_app())
    response = client.get("/teapot")
    assert response.status_code == status.HTTP_418_IM_A_TEAPOT
    payload = response.json()
    _assert_envelope(payload, "IM_A_TEAPOT")
    assert payload["error"]["message"] == "No coffee here."


def test_unexpected_error_returns_internal_envelope_without_leaking() -> None:
    # raise_server_exceptions=False makes TestClient return the 500 response the
    # catch-all handler produced instead of re-raising the RuntimeError.
    client = TestClient(_build_probe_app(), raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    _assert_envelope(response.json(), "INTERNAL_ERROR")
    assert "kaboom-secret" not in response.text
