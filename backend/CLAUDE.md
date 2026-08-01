# CLAUDE.md — Backend (FastAPI)

Guidance for the FastAPI backend under `backend/`. See the repo-root `CLAUDE.md` for cross-cutting orientation, the design-doc-driven / milestone-sequenced workflow, and the `docs/` map.

**The repo is in M1 ("Core domain").** The seven §5.2 tables and their migration exist; `rewatch/` is still an empty stub (M4). Do not add domain logic to a milestone that doesn't own it (see the out-of-scope table in `docs/milestones/MILESTONE_M1_V1.md`).

## Commands

All backend commands run from `backend/`.

Dependencies are managed with **uv** (`brew install uv`): the committed `uv.lock` pins exact versions (NFR-MAINT-04 reproducibility), and `uv sync` builds `.venv` from it — the app installed editable plus the `dev` group (pyright, pytest, httpx2). Never `pip install` into this project; add/upgrade dependencies via `uv add` / `uv lock --upgrade` so the lockfile moves with `pyproject.toml`.

```bash
uv sync                            # one-time setup (creates .venv from uv.lock, installs dev tools + httpx2)
make typecheck                     # uv run pyright — strict mode over app/ + tests/, must be zero errors
make lint                          # uv run ruff check — must be clean
make format-check                  # uv run ruff format --check (fix findings with `make format`)
make test                          # uv run pytest — needs the composed Postgres for the `db`-marked tests
make test-offline                  # uv run pytest -m "not db" — no database needed
uv run pytest tests/test_core_errors.py   # run one test file
uv run pytest tests/test_core_errors.py::test_name   # run one test
uv run uvicorn app.main:app --reload      # run the API locally (Swagger at /docs, schema at /openapi.json)
uv run alembic upgrade head               # apply migrations
uv run alembic revision --autogenerate    # after `upgrade head`: must produce an empty diff
```

There is no CI — `make typecheck`, `make lint`, `make format-check`, and `make test` are the local gate for every change (the repo-level pre-commit hook runs the Ruff pair on staged backend files). The strict type-check must pass with zero errors from the first commit; treat a pyright or Ruff error as a build break. Everything runs through `uv run`, which uses `backend/.venv` (syncing it first if stale) — no manual activation; pyright resolves types from that environment, so a run outside `uv run`/the venv reports spurious missing-import errors.

Running the app or Alembic requires `DATABASE_URL` (the tests set a placeholder — see Conventions). Copy `.env.example` to `.env` for local values.

## Architecture

### Layering (per feature module)

Each domain module (`app/<feature>/`) realises the three-layer architecture as **files, not folders**:

- `router.py` — presentation: HTTP routing and (de)serialisation only. **Never imports a repository.**
- `service.py` — business logic: validation, domain rules. No HTTP, no raw SQL/ORM specifics.
- `repository.py` — data access: CRUD over the SQLAlchemy ORM behind a stable interface. No business rules.
- `models.py` (ORM), `schemas.py` (Pydantic), `dependencies.py` (FastAPI DI wiring).

Within a module, calls flow `router → service → repository` (injected via FastAPI dependencies). **Cross-module calls go service-to-service**, never into another module's repository.

### Application assembly

`app/main.py` is an app factory (`create_app()`): it builds the FastAPI app, adds CORS from config, registers the error handlers, then assembles the `/api/v1` router in `build_api_router()`, mounting each module's router. There is **no** `app/adapters/` folder — the adapter pattern (§5.6) is future work, if ever; the layering (core logic never imports an adapter) is what keeps it hook-in-able, and the folder is created only together with the first adapter. It would then be an internal integration surface, never mounted as a public namespace.

### Cross-cutting `core/`

- `core/config.py` — `Settings` via `pydantic-settings`; everything environment-specific is read from env / `.env` (nothing hardcoded, NFR-MAINT-04). Access it through the cached `get_settings()`. Variable names map 1:1 to `.env.example`.
- `core/schemas.py` — `StrictSchema`, the base every request/response schema must inherit. It is `strict=True` (no lossy coercion — `"1"` is not accepted for an `int`) and `extra="forbid"`. **Gotcha:** because FastAPI validates request bodies on Pydantic's *Python* path, a bare `date`/`datetime`/`time`/`UUID` field rejects ISO-8601 strings under strict mode. For those fields use the provided aliases `JsonDate`, `JsonDateTime`, `JsonTime`, `JsonUUID` instead of the bare types.
- `core/errors.py` — the single error envelope `{ "error": { "code", "message" } }` (NFR-MAINT-03). `register_exception_handlers()` overrides FastAPI's defaults so **no route can emit another error shape**. Raise `AppError` (or, in M1+, a domain subclass overriding `code`/`status_code`/`message`) for controlled errors.
- `core/db.py` — SQLAlchemy 2.x plumbing: lazily-cached engine/session factory (importing this module never touches the DB), the request-scoped `get_session()` generator dependency, and the typed declarative `Base`. The seven domain models register on `Base.metadata`; the guard test `test_metadata_defines_exactly_the_seven_domain_tables` keeps a stray model from silently widening the schema.

### Migrations

Alembic lives in `backend/migrations/`. `env.py` reads `DATABASE_URL` from `core/config` (not from `alembic.ini`) and targets `Base.metadata`. `alembic.ini` intentionally has no `sqlalchemy.url`.

## Conventions

- **Type safety is strict everywhere** (§5.7): pyright strict statically, Pydantic strict at the API boundary, SQLAlchemy 2.x `Mapped[...]` on ORM columns.
- **Docstrings** cite design sections and requirement IDs (`§5.2`, `NFR-MAINT-03`) as pointers, not paraphrases. Length and placement follow the `code-docs` skill.
- **Lint/format is Ruff** (REVIEW_M0 §4): `ruff check` and `ruff format --check` must be clean — config in `pyproject.toml` (`[tool.ruff]`, line length 100, `extend-select` E/W/F/I/UP/B/C4/RUF). Never hand-format against the formatter; run `make format`.
- **Tests** (`backend/tests/`): `conftest.py` sets a placeholder `DATABASE_URL` via `os.environ.setdefault` so the app can be built offline; real HTTP tests drive the app through Starlette's `TestClient`, which requires **`httpx2`** (already in the `[dev]` deps) — plain `httpx` will make strict pyright fail. Repository tests run against a real Postgres via the `db_session` fixture (§9) — see the README for the database setup.
