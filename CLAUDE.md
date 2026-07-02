# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Orientation

FilmRewatchApp is a two-tier film-tracking app: an Angular PWA client and a FastAPI backend, communicating over a versioned `/api/v1` HTTP/JSON API. Only the **backend** exists so far; the Angular workspace is not yet created.

Development is **design-doc-driven and milestone-sequenced**. Before writing feature code, read the relevant sections of `docs/`:
- `docs/designs/DESIGN_V1.md` — the authoritative technical design. Code and commit messages reference its sections (`§5.1`, `§5.7`) and requirement IDs (`NFR-MAINT-03`, `FR-LIB-04`) pervasively; keep doing so.
- `docs/milstones/MILESTONE_M0_V1.md` — the current milestone (M0, "Scaffolding"), broken into per-PR work items with acceptance criteria and an explicit out-of-scope list.
- `docs/requierements/REQUIEREMENTS_V1.md` (note the spelling), `docs/requierements/OPEN_DECISIONS_V1.md`, `docs/requierements/FUTURE_WORK_V1.md`.

**The repo is currently in M0.** Every feature module under `backend/app/` (`films/`, `ratings/`, `tags/`, `genres/`, `rewatch/`) is an intentional **empty stub** — the layout exists but there is no domain behaviour, no ORM tables, and no real routes. Those arrive in M1+. Do not add domain logic to a milestone that doesn't own it (see the out-of-scope table in the milestone doc).

## Commands

All backend commands run from `backend/`.

```bash
pip install -e .[dev]              # one-time setup (installs dev tools + httpx2)
make typecheck                     # pyright in strict mode over app/ + tests/ — must be zero errors
make test                          # pytest
pytest tests/test_core_errors.py   # run one test file
pytest tests/test_core_errors.py::test_name   # run one test
uvicorn app.main:app --reload      # run the API locally (Swagger at /docs, schema at /openapi.json)
alembic upgrade head               # apply migrations (M0: empty baseline only)
alembic revision --autogenerate    # M0: must produce an empty diff (no models yet)
```

There is no CI — `make typecheck` and `make test` are run locally and are the gate for every change. The strict type-check must pass with zero errors from the first commit; treat a pyright error as a build break.

Running the app or Alembic requires `DATABASE_URL` (and the tests set a placeholder — see below). Copy `backend/.env.example` to `backend/.env` for local values.

## Architecture

### Layering (per feature module)

Each domain module (`app/<feature>/`) realises the three-layer architecture as **files, not folders**:

- `router.py` — presentation: HTTP routing and (de)serialisation only. **Never imports a repository.**
- `service.py` — business logic: validation, domain rules. No HTTP, no raw SQL/ORM specifics.
- `repository.py` — data access: CRUD over the SQLAlchemy ORM behind a stable interface. No business rules.
- `models.py` (ORM), `schemas.py` (Pydantic), `dependencies.py` (FastAPI DI wiring).

Within a module, calls flow `router → service → repository` (injected via FastAPI dependencies). **Cross-module calls go service-to-service**, never into another module's repository.

### Application assembly

`app/main.py` is an app factory (`create_app()`): it builds the FastAPI app, adds CORS from config, registers the error handlers, then assembles the `/api/v1` router in `build_api_router()`, mounting each module's router. `app/adapters/` is an internal integration surface (§5.6) and is deliberately **not** mounted as a public namespace.

### Cross-cutting `core/`

- `core/config.py` — `Settings` via `pydantic-settings`; everything environment-specific is read from env / `.env` (nothing hardcoded, NFR-MAINT-04). Access it through the cached `get_settings()`. Variable names map 1:1 to `.env.example`.
- `core/schemas.py` — `StrictSchema`, the base every request/response schema must inherit. It is `strict=True` (no lossy coercion — `"1"` is not accepted for an `int`) and `extra="forbid"`. **Gotcha:** because FastAPI validates request bodies on Pydantic's *Python* path, a bare `date`/`datetime`/`time`/`UUID` field rejects ISO-8601 strings under strict mode. For those fields use the provided aliases `JsonDate`, `JsonDateTime`, `JsonTime`, `JsonUUID` instead of the bare types.
- `core/errors.py` — the single error envelope `{ "error": { "code", "message" } }` (NFR-MAINT-03). `register_exception_handlers()` overrides FastAPI's defaults so **no route can emit another error shape**. Raise `AppError` (or, in M1+, a domain subclass overriding `code`/`status_code`/`message`) for controlled errors.
- `core/db.py` — SQLAlchemy 2.x plumbing: lazily-cached engine/session factory (importing this module never touches the DB), the request-scoped `get_session()` generator dependency, and the typed declarative `Base`. **`Base.metadata` is empty in M0** — this is what keeps `alembic revision --autogenerate` an empty diff; the guard test `test_baseline_defines_no_tables` protects that invariant. Domain models register on `Base.metadata` in M1.

### Migrations

Alembic lives in `backend/migrations/`. `env.py` reads `DATABASE_URL` from `core/config` (not from `alembic.ini`) and targets `Base.metadata`. `alembic.ini` intentionally has no `sqlalchemy.url`.

## Conventions

- **Type safety is strict everywhere** (§5.7): pyright strict statically, Pydantic strict at the API boundary, SQLAlchemy 2.x `Mapped[...]` on ORM columns. Match the existing heavily-documented module-docstring style that cites design sections and requirement IDs.
- **Tests** (`backend/tests/`): `conftest.py` sets a placeholder `DATABASE_URL` via `os.environ.setdefault` so the app can be built offline; real HTTP tests drive the app through Starlette's `TestClient`, which requires **`httpx2`** (already in the `[dev]` deps) — plain `httpx` will make strict pyright fail.
