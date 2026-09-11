"""Single API error envelope and the handlers that enforce it (DESIGN §5.4).

Every error the API returns — an application/domain failure, a request-validation
failure, a Starlette ``HTTPException`` (e.g. the 404 for an unknown route), or an
unexpected crash — is serialised to exactly one shape (NFR-MAINT-03)::

    { "error": { "code": "<STABLE_TOKEN>", "message": "<human-readable>" } }

``code`` is a stable, machine-readable token the client branches on; ``message``
is a human-readable, safe-to-surface summary. The app factory (``app/main.py``)
calls :func:`register_exception_handlers`, which overrides FastAPI's defaults so
**no route can bypass the envelope**.

M0 shipped only generic, framework-level codes: ``VALIDATION_ERROR`` for a
request-validation failure, the HTTP status name for an ``HTTPException`` (e.g.
404 → ``NOT_FOUND``), and ``INTERNAL_ERROR`` for an unexpected crash. M1 adds
domain codes as :class:`AppError` subclasses, one per feature module. The
single, stable inventory (NFR-MAINT-01/03) — every code any M1 route can
return, and why:

======================  =====  ==========================================
Code                    HTTP   Raised by
======================  =====  ==========================================
``VALIDATION_ERROR``    422    Request-schema failures; also
                               ``FilmIdCollisionError``, ``InvalidTagNameError``,
                               ``InvalidGenreNameError`` (domain rules that
                               are still "the payload was invalid")
``NOT_FOUND``           404    Unknown route; ``FilmNotFoundError``,
                               ``RatingNotFoundError``
``DUPLICATE_FILM``      409    ``DuplicateFilmError`` (FR-LIB-05/09)
``FUTURE_WATCH_DATE``   422    ``FutureWatchDateError`` (FR-RAT-03)
``INTERNAL_ERROR``      500    Unexpected crash; a genuine race past the
                               natural-key pre-check (§3.6)
======================  =====  ==========================================

:func:`error_responses` turns a ``{status_code: [codes]}`` mapping into the
FastAPI ``responses=`` kwarg, documenting :class:`ErrorResponse` as the schema
for that status — including overriding FastAPI's automatically-added 422
entry, which otherwise advertises its own default validation-error shape
instead of this API's actual envelope.
"""

from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.schemas import StrictSchema


class ErrorDetail(StrictSchema):
    """The ``code``/``message`` pair carried inside the envelope."""

    code: str
    message: str


class ErrorResponse(StrictSchema):
    """The single envelope every error response is serialised to."""

    error: ErrorDetail


class AppError(Exception):
    """Base application error rendered as the standard envelope.

    Raise this — or, in M1+, a domain subclass that overrides the class
    attributes — to return a controlled error with a stable ``code`` and HTTP
    ``status_code``. The message may be overridden per-instance::

        class DuplicateFilmError(AppError):
            code = "DUPLICATE_FILM"
            status_code = status.HTTP_409_CONFLICT
            message = "A film with this title and year already exists."
    """

    code: str = "INTERNAL_ERROR"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


def _code_for_status(status_code: int) -> str:
    """Map an HTTP status to a stable code token (404 → ``NOT_FOUND``)."""
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return "HTTP_ERROR"


def _envelope(
    status_code: int,
    code: str,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Serialise ``code``/``message`` into the envelope as a ``JSONResponse``."""
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    """Render an :class:`AppError` (or subclass) as the envelope."""
    # Starlette only routes ``AppError`` instances here; the narrowing satisfies
    # the handler protocol, which is typed against the broad ``Exception``.
    assert isinstance(exc, AppError)
    return _envelope(exc.status_code, exc.code, exc.message)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Reshape FastAPI's request-validation failure into a 422 envelope.

    The per-field error list is intentionally not surfaced — the envelope is
    exactly ``{ code, message }`` (NFR-MAINT-03); a richer detail channel, if
    ever needed, is a later, separate concern.
    """
    assert isinstance(exc, RequestValidationError)
    return _envelope(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Request validation failed.",
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Reshape a Starlette/FastAPI ``HTTPException`` into the envelope.

    The code is the HTTP status name (404 → ``NOT_FOUND``); the exception's
    headers are preserved so responses like a 405's ``Allow`` still reach the
    client. ``detail`` is coerced to ``str`` in case a caller passed a non-string.
    """
    assert isinstance(exc, StarletteHTTPException)
    return _envelope(
        exc.status_code,
        _code_for_status(exc.status_code),
        str(exc.detail),
        exc.headers,
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: render any unhandled exception as a 500 envelope.

    The exception is deliberately not leaked to the client. Starlette's
    ``ServerErrorMiddleware`` still re-raises it after this response is sent, so
    the server logs the traceback for the developer.
    """
    return _envelope(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR",
        "An unexpected error occurred.",
    )


def error_responses(
    codes_by_status: Mapping[int, Sequence[str]],
) -> dict[int | str, dict[str, Any]]:
    """Build an OpenAPI ``responses=`` mapping documenting the single envelope.

    ``codes_by_status`` is ``{status_code: [domain codes possible at that
    status]}`` — a route that can return ``DUPLICATE_FILM`` (409) and
    ``NOT_FOUND``/``VALIDATION_ERROR`` (from the table above) passes
    ``{409: ["DUPLICATE_FILM"], 404: ["NOT_FOUND"], 422: ["VALIDATION_ERROR"]}``.
    Every entry documents :class:`ErrorResponse` as the schema, so Swagger and
    ``/openapi.json`` show the envelope actually returned — this also
    overrides FastAPI's automatically-generated 422 entry (see module
    docstring), which otherwise documents the wrong shape for every route with
    a body or typed parameter.
    """
    return {
        status_code: {
            "model": ErrorResponse,
            "description": " / ".join(f"`{code}`" for code in codes),
        }
        for status_code, codes in codes_by_status.items()
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register the envelope handlers on the app (called by the app factory).

    The four handlers — application errors, request validation, ``HTTPException``,
    and the catch-all — override FastAPI's defaults so every error response, from
    any route, uses the single envelope (NFR-MAINT-03).
    """
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)
