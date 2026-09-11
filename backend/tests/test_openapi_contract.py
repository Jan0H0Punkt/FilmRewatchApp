"""M1 OpenAPI documentation + error-envelope contract audit (M1 PR8, NFR-MAINT-01/03).

M0's PR5 (``test_core_errors.py``) proved the envelope handlers are wired on
the real app; the M1 feature PRs each proved their own routes' individual
error paths return the right *code* end to end (``test_films_api.py`` and
friends). What was still missing after PR7: proof that ``/openapi.json`` —
the artefact ``NFR-MAINT-01`` actually cares about — documents that surface
*correctly*. FastAPI auto-adds a 422 response to every route with a body or
typed parameter, described with its own default ``HTTPValidationError``
schema, regardless of what the registered handlers actually return; before
this PR every M1 route's docs silently disagreed with its real behaviour, and
no route documented its 404/409 paths at all.

This module is offline (``create_app().openapi()`` builds the schema without
touching a database) and audits three things:

1. every M1 route is present under the ``v1`` namespace;
2. every documented non-2xx response references the single ``ErrorResponse``
   schema — never FastAPI's default validation-error shape;
3. the full domain-code inventory actually defined in code (every
   :class:`~app.core.errors.AppError` subclass's ``code``, plus the three
   framework-level codes) is documented on at least one route — so a new
   domain error that forgets its route's ``responses=`` fails this test
   instead of silently drifting out of the docs.
"""

from typing import cast

from app.core.errors import AppError
from app.main import create_app

_M1_ROUTES = {
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/films"),
    ("POST", "/api/v1/films/duplicate-check"),
    ("GET", "/api/v1/films/{film_id}"),
    ("PATCH", "/api/v1/films/{film_id}"),
    ("DELETE", "/api/v1/films/{film_id}"),
    ("POST", "/api/v1/films/{film_id}/ratings"),
    ("DELETE", "/api/v1/ratings/{rating_id}"),
    ("GET", "/api/v1/tags"),
    ("GET", "/api/v1/genres"),
}

# The framework-level codes core/errors.py's handlers can emit without a
# dedicated AppError subclass: a bare HTTPException (404s on an unregistered
# id) or a plain request-validation failure — see that module's docstring
# table. ``INTERNAL_ERROR`` is deliberately excluded: it is the catch-all 500
# for an unexpected crash, an implicit whole-API guarantee rather than a
# specific route's documented contract, so no route's ``responses=`` claims it.
_FRAMEWORK_CODES = {"VALIDATION_ERROR", "NOT_FOUND"}


def _schema() -> dict[str, object]:
    return create_app().openapi()


def _paths(schema: dict[str, object]) -> dict[str, dict[str, dict[str, object]]]:
    return cast(dict[str, dict[str, dict[str, object]]], schema["paths"])


def test_every_m1_route_is_documented_under_the_v1_namespace() -> None:
    schema = _schema()
    documented = {
        (method.upper(), path) for path, methods in _paths(schema).items() for method in methods
    }
    missing = _M1_ROUTES - documented
    assert not missing, f"undocumented M1 routes: {missing}"


def test_no_route_documents_fastapis_default_validation_error_shape() -> None:
    # The concrete gap this PR closed: FastAPI's auto-added 422 previously
    # pointed at its own HTTPValidationError, not the app's real envelope.
    schema = _schema()
    components = cast(dict[str, object], schema.get("components", {}))
    assert "HTTPValidationError" not in cast(dict[str, object], components.get("schemas", {}))


def test_every_documented_error_response_references_the_single_envelope() -> None:
    schema = _schema()
    for path, methods in _paths(schema).items():
        if not path.startswith("/api/v1/"):
            continue
        for method, operation in methods.items():
            responses = cast(dict[str, dict[str, object]], operation["responses"])
            for status_code, response in responses.items():
                if status_code.startswith("2"):
                    continue
                content = cast(dict[str, object], response.get("content", {}))
                media = cast(dict[str, object], content.get("application/json", {}))
                schema_ref = cast(dict[str, str], media.get("schema", {})).get("$ref")
                assert schema_ref == "#/components/schemas/ErrorResponse", (
                    f"{method.upper()} {path} {status_code} references {schema_ref!r}, "
                    "not the single ErrorResponse envelope"
                )


def _documented_codes(schema: dict[str, object]) -> set[str]:
    """Every domain code named in a response ``description`` (the format
    ``error_responses()`` writes: `` "`CODE_A` / `CODE_B`" ``)."""
    codes: set[str] = set()
    for path, methods in _paths(schema).items():
        if not path.startswith("/api/v1/"):
            continue
        for operation in methods.values():
            for response in cast(dict[str, dict[str, object]], operation["responses"]).values():
                description = cast(str, response.get("description", ""))
                if not description.startswith("`"):
                    continue
                codes.update(part.strip("`") for part in description.split(" / "))
    return codes


def test_every_domain_code_defined_in_code_is_documented_on_some_route() -> None:
    # ``__subclasses__()`` reflects every subclass loaded anywhere in the
    # process — including throwaway ones other test modules define (e.g.
    # test_core_errors.py's stand-in teapot error) — so this is restricted to
    # subclasses the app itself defines, or the result depends on test order.
    defined_codes = {
        subclass.code
        for subclass in AppError.__subclasses__()
        if subclass.__module__.startswith("app.")
    } | _FRAMEWORK_CODES
    documented_codes = _documented_codes(_schema())
    assert documented_codes == defined_codes
