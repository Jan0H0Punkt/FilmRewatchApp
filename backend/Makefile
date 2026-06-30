# Backend developer tasks (DESIGN §8.1, §5.7). Run from `backend/`.
# One-time setup:  pip install -e .[dev]

.PHONY: typecheck test

# Strict static type-check over the whole backend (pyright, §5.7). Config lives
# in pyproject.toml's [tool.pyright]; this is the one-command target (PR8 docs it).
typecheck:
	pyright

# Unit tests.
test:
	pytest
