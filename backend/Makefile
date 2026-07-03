# Backend developer tasks (DESIGN §8.1, §5.7). Run from `backend/`.
# One-time setup:  pip install -e .[dev]

.PHONY: typecheck test migrate

# Strict static type-check over the whole backend (pyright, §5.7). Config lives
# in pyproject.toml's [tool.pyright]; this is the one-command target (PR8 docs it).
typecheck:
	pyright

# Unit tests.
test:
	pytest

# Apply Alembic migrations up to head against DATABASE_URL (M0: the empty
# baseline only — domain tables arrive in M1). Needs a reachable Postgres,
# e.g. `docker compose up postgres` publishing 5432 to the host.
migrate:
	alembic upgrade head
