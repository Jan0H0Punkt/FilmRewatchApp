# FilmRewatchApp

A personal film-tracking web application: log the films you've watched, rate and tag them, and get
daily suggestions for what to rewatch. It is a **two-tier** app — an Angular PWA client and a
Python/FastAPI backend with PostgreSQL — communicating exclusively over a versioned `/api/v1`
HTTP/JSON API. It is designed to run entirely on your own machine via Docker Compose, with the PWA
installable on a phone over the LAN.

> **Status: Milestone M1 — Core Domain (backend).** The backend now has a working core domain:
> log a watched film — atomically, with its mandatory first rating, tags, and genres — read it
> back in full, edit it, rate it again, and delete it, with every data-model rule
> ([REQUIREMENTS §4](docs/requirements/REQUIREMENTS_V1.md#4-data-model)) enforced server-side. M1
> is backend-only; listing/search (`GET /films`), the frontend, and rewatch suggestions are later
> milestones — see [docs/milestones/MILESTONE_M1_V1.md](docs/milestones/MILESTONE_M1_V1.md).

## Quick start (Docker)

Requires Docker with the Compose plugin.

```bash
docker compose up        # or: make up
```

This starts **PostgreSQL 17 + the backend** as one stack. The backend applies database migrations
on startup (the M1 seven-table schema — DESIGN §5.2) and reports healthy once
`GET /api/v1/health` returns `200`.

Then open http://localhost:8000/docs (**Swagger UI**) to try the API interactively, or
http://localhost:8000/openapi.json for the raw schema. The M1 surface:

| Route | What |
| --- | --- |
| `GET /api/v1/health` | Liveness probe |
| `POST /api/v1/films` | Log a watched film — atomically, with its first rating, ≥1 tag, ≥1 genre |
| `POST /api/v1/films/duplicate-check` | Side-effect-free probe for a colliding film |
| `GET /api/v1/films/{id}` | Full detail read — titles, genres, tags, rating history, computed average |
| `PATCH /api/v1/films/{id}` | Edit a film's user-editable fields |
| `DELETE /api/v1/films/{id}` | Delete a film, cascading its titles/ratings/links, reaping orphan labels |
| `POST /api/v1/films/{id}/ratings` | Add a rating to an existing film |
| `DELETE /api/v1/ratings/{id}` | Delete a rating — deleting a film's last rating deletes the film |
| `GET /api/v1/tags` / `GET /api/v1/genres` | Prefix-filterable lookups for autocomplete |

Every error response — including domain codes like `DUPLICATE_FILM` and `FUTURE_WATCH_DATE` — uses
the single envelope `{ "error": { "code", "message" } }`; Swagger documents the exact codes each
route can return. `GET /films` (list/search/filter/sort) is **M2**; the frontend is **M3**.

Database data survives `docker compose down && docker compose up` (named volume `pgdata`).
Nothing environment-specific is hardcoded (§3.5 config-over-code): the compose file has working
defaults, and you can override e.g. the allowed frontend origin from the shell:

```bash
CORS_ALLOWED_ORIGINS=http://192.168.1.10:4200 docker compose up
```

For persistent overrides, copy the root [`.env.example`](.env.example) to `.env` — Docker Compose
reads it automatically (DB credentials, CORS origins; every variable is documented there). This is
a *different* file from `backend/.env`, which the app reads when run outside Docker.

## Local development (backend)

Requires [uv](https://docs.astral.sh/uv/) (`brew install uv`) and Python ≥ 3.12 (uv fetches one if
needed). Dependencies are pinned in the committed `uv.lock`, so every environment — including the
Docker image — installs exactly the same versions (NFR-MAINT-04). All commands run from `backend/`.

```bash
cd backend
uv sync                      # one-time setup — creates .venv from uv.lock (app + dev tools)
cp .env.example .env         # local config — every variable is documented there
```

Run the API against the composed Postgres (`docker compose up postgres` gives you just the DB):

```bash
make migrate                            # alembic upgrade head (the M1 seven-table schema)
uv run uvicorn app.main:app --reload    # Swagger at http://localhost:8000/docs
```

### Tests, type-check & lint

There is no CI — these commands are the **local gate for every change**:

```bash
make test          # full pytest suite — includes the DB-bound repository tests (§9)
make test-offline  # offline subset only (pytest -m "not db"; no database needed)
make typecheck     # pyright in strict mode (§5.7) — must be zero errors
make lint          # ruff check — must be clean
make format-check  # ruff format --check (fix findings with `make format`)
```

Repository tests run against a **real Postgres** (DESIGN §9): a disposable
`filmrewatch_test` database on the composed server, recreated and migrated per run — dev data in
`filmrewatch` is never touched. Start the database with `docker compose up postgres`; when it is
down, the `db`-marked tests **skip with a reason** and the offline subset still passes. A
non-default server/credentials setup can point `TEST_DATABASE_URL` at another Postgres (that
database is owned — and dropped — by the suite).

Strict type-safety is enforced from the first commit: treat a pyright or Ruff error as a build
break. The make targets run through `uv run`, which resolves the tools from `backend/.venv` — no
manual activation needed. To change dependencies, use `uv add` / `uv lock --upgrade` (never bare
`pip`), so `uv.lock` stays in step with `pyproject.toml`.

## Local development (frontend)

Requires Node.js ≥ 20. All commands run from `frontend/`.

```bash
npm install        # one-time setup
npm start          # dev server at http://localhost:4200 (uses environment.development.ts)
npm run build      # production build — strict TS type-check included, must be clean
npm test           # vitest unit tests
npm run lint       # ESLint, incl. template a11y rules
```

The API base URL is hard-coded in the build (§8 wiring): `src/environments/environment.ts` is the
single wiring point (the laptop's LAN address so the mobile PWA can reach it); `ng serve` swaps in
a localhost variant. The backend's `CORS_ALLOWED_ORIGINS` must include this app's origin.

Once per clone, enable the repo's pre-commit hook (Prettier + ESLint on staged frontend files,
Ruff lint + format check on staged backend Python files):

```bash
git config core.hooksPath .githooks
```

## Make targets

All targets run from the repo root; the backend ones also run from `backend/` (the root
`Makefile` delegates to it; backend targets run through `uv run`, no activation needed):

| Command             | What it does                                                                          |
| ------------------- | ------------------------------------------------------------------------------------- |
| `make dev`          | Start the whole app: Docker stack (detached, waits healthy) + Angular dev server      |
| `make up`           | Start the backend stack (backend + PostgreSQL) via Docker Compose, in the foreground  |
| `make down`         | Stop the Docker Compose stack (data survives — named volume)                          |
| `make check`        | The full local gate: backend typecheck + lint + format + tests, frontend build + tests + lint |
| `make typecheck`    | pyright in strict mode over the whole backend — must be zero errors                   |
| `make lint`         | Ruff lint over the whole backend — must be clean                                      |
| `make format-check` | Ruff format check (`make -C backend format` rewrites)                                 |
| `make test`         | Backend tests incl. DB-bound (frontend tests: `npm test` from `frontend/`)            |
| `make test-offline` | Backend offline tests only — skips the `db`-marked repository tests (§9)              |
| `make migrate`      | Apply Alembic migrations to the DB in `DATABASE_URL`                                  |

`make dev` leaves the containers running when you Ctrl+C the dev server — stop them with
`make down`. `make check` is the everything-bar before merging: it needs both toolchains
(`uv` installed + `frontend/node_modules` installed) and stops at the first failure.

## Repository layout

The physical layout enforces the three-layer architecture — see
[DESIGN §4 Repository Layout](docs/designs/DESIGN_V1.md#4-repository-layout) for the authoritative
map.

```
backend/     FastAPI service — app/<feature>/ modules (router → service → repository),
             cross-cutting app/core/, Alembic migrations/, tests/. See backend/CLAUDE.md.
frontend/    Angular PWA client — views/ → domain/<entity>/ facades → core/, shared/,
             route-registry stub (§6.5). See frontend/CLAUDE.md.
docs/        Design doc, milestone plans, requirements — see below.
```

## Versioning

The app follows [Semantic Versioning 2.0.0](https://semver.org) (`MAJOR.MINOR.PATCH`). The
"public API" in SemVer's sense is the versioned HTTP contract the client consumes (`/api/v1`):

- **MAJOR** — incompatible changes to the public API. A breaking change also moves the URL
  contract (`/api/v1` → `/api/v2`), so the app major and the URL version move together.
- **MINOR** — new, backwards-compatible functionality. Pre-1.0, each completed milestone bumps
  it (M1 → `0.2.0`, M2 → `0.3.0`, …).
- **PATCH** — backwards-compatible bug fixes.

The current version is **0.2.0** (M1 core domain). Per SemVer, `0.x` is the development phase —
anything may change at any time. **`1.0.0`** declares the public API stable and is reserved for
when [REQUIREMENTS_V1.md](docs/requirements/REQUIREMENTS_V1.md) is fully implemented (Future Work
excluded).

## Documentation

Development is **design-doc-driven and milestone-sequenced**; code and commits reference design
sections (`§5.7`) and requirement IDs (`NFR-MAINT-03`) throughout.

- [docs/designs/DESIGN_V1.md](docs/designs/DESIGN_V1.md) — the authoritative technical design
  (stack, architecture, API contract, delivery plan).
- [docs/milestones/MILESTONE_M1_V1.md](docs/milestones/MILESTONE_M1_V1.md) — the current milestone,
  broken into per-PR work items with acceptance criteria
  ([MILESTONE_M0_V1.md](docs/milestones/MILESTONE_M0_V1.md) is its complete predecessor).
- [docs/requirements/REQUIREMENTS_V1.md](docs/requirements/REQUIREMENTS_V1.md) — functional and
  non-functional requirements, with
  [OPEN_DECISIONS_V1.md](docs/requirements/OPEN_DECISIONS_V1.md) and
  [FUTURE_WORK_V1.md](docs/requirements/FUTURE_WORK_V1.md).
