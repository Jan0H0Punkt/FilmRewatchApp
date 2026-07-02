# Production-style image for the FastAPI backend (DESIGN §8.1, M0 PR6).
#
# Built and run by the repo-root docker-compose.yml as one `docker compose up`
# stack together with PostgreSQL (§8.2 deployment target: the user's laptop).
# Nothing environment-specific is baked in — DATABASE_URL, CORS_ALLOWED_ORIGINS,
# HOST and PORT are injected at runtime (§3.5 config-over-code, NFR-MAINT-04).

# python:3.12 matches pyproject's `requires-python = ">=3.12"` and pyright's
# `pythonVersion` (§5.7), so the image runs what the strict check certifies.
FROM python:3.12-slim

# No .pyc litter in the image; logs unbuffered so `docker logs` sees them live.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# The application package plus what the startup `alembic upgrade head` needs:
# the migration scripts and alembic.ini, whose relative `script_location` /
# `prepend_sys_path` resolve against this WORKDIR exactly as they do when
# Alembic runs from `backend/` locally. (`.dockerignore` keeps .env, venvs and
# tests out of the build context.)
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN pip install --no-cache-dir .

# The app needs no root privileges — run as an unprivileged system user.
RUN useradd --system --no-create-home appuser
USER appuser

# Server bind (DESIGN §8.1) — defaults mirror .env.example; override via env.
ENV HOST=0.0.0.0 \
    PORT=8000
EXPOSE 8000

# Apply migrations before serving, so a fresh `up` is immediately consistent
# (M0: the empty baseline — Alembic's version table only, no domain tables).
# `exec` hands PID 1 to uvicorn so it receives the container's stop signal.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host \"$HOST\" --port \"$PORT\""]
