# Backend developer tasks (DESIGN §8.1, §5.7). Run from `backend/`.
# One-time setup:  uv sync   (creates .venv from the committed uv.lock)
#
# Every target goes through `uv run`, which resolves tools from the project
# venv (syncing it first if stale) — no manual activation needed.

.PHONY: typecheck lint format format-check test test-offline migrate

# Strict static type-check over the whole backend (pyright, §5.7). Config lives
# in pyproject.toml's [tool.pyright]; this is the one-command target (PR8 docs it).
typecheck:
	uv run pyright

# Ruff lint (REVIEW_M0 §4) — config in pyproject.toml's [tool.ruff.lint].
lint:
	uv run ruff check .

# Ruff formatter: `format` rewrites, `format-check` verifies (the gate and the
# pre-commit hook run the check; run `make format` to fix findings).
format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

# Full test suite (§9, M1 PR2): the offline tests plus the DB-bound repository
# tests, which run against the composed Postgres (`docker compose up postgres`)
# and skip with a reason when it is down.
test:
	uv run pytest

# Offline subset only — excludes the `db`-marked repository tests; no database
# needed (the placeholder DATABASE_URL from tests/conftest.py suffices).
test-offline:
	uv run pytest -m "not db"

# Apply Alembic migrations up to head against DATABASE_URL (M0: the empty
# baseline only — domain tables arrive in M1). Needs a reachable Postgres,
# e.g. `docker compose up postgres` publishing 5432 to the host.
migrate:
	uv run alembic upgrade head
