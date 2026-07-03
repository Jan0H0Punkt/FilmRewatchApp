# FilmRewatchApp

A personal film-tracking web application: log the films you've watched, rate and tag them, and get
daily suggestions for what to rewatch. It is a **two-tier** app — an Angular PWA client and a
Python/FastAPI backend with PostgreSQL — communicating exclusively over a versioned `/api/v1`
HTTP/JSON API. It is designed to run entirely on your own machine via Docker Compose, with the PWA
installable on a phone over the LAN.

> **Status: Milestone M0 — Scaffolding.** The repo currently contains the backend's empty, runnable
> shell: layout, config, strict typing, migrations harness, error envelope, and the Docker stack.
> There is deliberately **no domain behaviour yet** (no entities, no business rules, no screens) —
> that arrives in M1+. The Angular workspace (`frontend/`) is not yet created (M0 PR7).
> See [docs/milestones/MILESTONE_M0_V1.md](docs/milestones/MILESTONE_M0_V1.md).

## Quick start (Docker)

Requires Docker with the Compose plugin.

```bash
docker compose up
```

This starts **PostgreSQL 17 + the backend** as one stack. The backend applies database migrations
on startup (an empty baseline in M0) and reports healthy once `GET /api/v1/health` returns `200`.

Then open:

| URL | What |
| --- | --- |
| http://localhost:8000/api/v1/health | Liveness endpoint (the only route in M0) |
| http://localhost:8000/docs | **API docs** — Swagger UI |
| http://localhost:8000/openapi.json | OpenAPI schema |

Database data survives `docker compose down && docker compose up` (named volume `pgdata`).
Nothing environment-specific is hardcoded (§3.5 config-over-code): the compose file has working
defaults, and you can override e.g. the allowed frontend origin from the shell:

```bash
CORS_ALLOWED_ORIGINS=http://192.168.1.10:4200 docker compose up
```

## Local development (backend)

Requires Python ≥ 3.12. All commands run from `backend/`.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]        # one-time setup
cp .env.example .env         # local config — every variable is documented there
```

Run the API against the composed Postgres (`docker compose up postgres` gives you just the DB):

```bash
alembic upgrade head               # apply migrations (M0: empty baseline)
uvicorn app.main:app --reload      # Swagger at http://localhost:8000/docs
```

### Tests & type-check

There is no CI — these two commands are the **local gate for every change**:

```bash
make test          # pytest
make typecheck     # pyright in strict mode (§5.7) — must be zero errors
```

Strict type-safety is enforced from the first commit: treat a pyright error as a build break. Run
`make typecheck` with the virtualenv **activated**, since pyright resolves types from the active
environment.

## Repository layout

The physical layout enforces the three-layer architecture — see
[DESIGN §4 Repository Layout](docs/designs/DESIGN_V1.md#4-repository-layout) for the authoritative
map.

```
backend/     FastAPI service — app/<feature>/ modules (router → service → repository),
             cross-cutting app/core/, Alembic migrations/, tests/. See backend/CLAUDE.md.
frontend/    Angular PWA client — not yet created (M0 PR7).
docs/        Design doc, milestone plans, requirements — see below.
```

## Documentation

Development is **design-doc-driven and milestone-sequenced**; code and commits reference design
sections (`§5.7`) and requirement IDs (`NFR-MAINT-03`) throughout.

- [docs/designs/DESIGN_V1.md](docs/designs/DESIGN_V1.md) — the authoritative technical design
  (stack, architecture, API contract, delivery plan).
- [docs/milestones/MILESTONE_M0_V1.md](docs/milestones/MILESTONE_M0_V1.md) — the current milestone,
  broken into per-PR work items with acceptance criteria.
- [docs/requirements/REQUIEREMENTS_V1.md](docs/requirements/REQUIEREMENTS_V1.md) — functional and
  non-functional requirements, with
  [OPEN_DECISIONS_V1.md](docs/requirements/OPEN_DECISIONS_V1.md) and
  [FUTURE_WORK_V1.md](docs/requirements/FUTURE_WORK_V1.md).
