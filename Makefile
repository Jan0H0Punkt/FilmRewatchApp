# Repo-level developer entry points — the single dev loop that ties M0 together
# (M0 PR8; DESIGN §8.1: checks run locally via a make/script target, NFR-MAINT-05).
#
# The backend targets delegate to backend/Makefile, which runs everything
# through `uv run` (resolves pyright/pytest/alembic from backend/.venv — no
# activation needed). Frontend steps use its npm scripts via `npm --prefix frontend`.

.PHONY: dev up down check typecheck lint format-check test test-offline migrate

# Start the whole app: backend + PostgreSQL in Docker (detached, waits until
# healthy), then the Angular dev server in the foreground at localhost:4200.
# Ctrl+C stops the dev server; the containers keep running — `make down`.
dev:
	docker compose up --wait
	npm --prefix frontend start

# Run the backend stack (backend + PostgreSQL) via Docker Compose (PR6, §8.1).
up:
	docker compose up

# Stop the Docker Compose stack (data survives — named volume, PR6).
down:
	docker compose down

# The full local gate — build everything, run every check and every test on
# both tiers (there is no CI; this is the pre-merge bar). Backend half via the
# prerequisites (typecheck + lint + format + tests, mirroring the frontend's
# build + lint + tests); frontend per its CLAUDE.md gate: build (includes the
# strict TS type-check) + unit tests + lint.
check: typecheck lint format-check test
	npm --prefix frontend run build
	npm --prefix frontend test
	npm --prefix frontend run lint

# Strict pyright over the whole backend (§5.7) — must be zero errors.
typecheck:
	$(MAKE) -C backend typecheck

# Ruff lint over the backend (REVIEW_M0 §4; frontend lint runs inside `check`).
lint:
	$(MAKE) -C backend lint

# Ruff format check over the backend (`make -C backend format` rewrites).
format-check:
	$(MAKE) -C backend format-check

# Backend tests, full suite: offline plus the DB-bound repository tests (§9),
# which need the composed Postgres up and skip with a reason otherwise.
# (Frontend unit tests run via `npm test` from frontend/.)
test:
	$(MAKE) -C backend test

# Backend offline subset only — skips the `db`-marked repository tests.
test-offline:
	$(MAKE) -C backend test-offline

# Apply Alembic migrations to the DB in DATABASE_URL (M0: empty baseline).
migrate:
	$(MAKE) -C backend migrate
