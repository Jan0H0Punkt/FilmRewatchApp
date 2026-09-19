"""Application configuration (DESIGN §3.5 config-over-code, §8).

Every environment-specific value is read from the environment — or a local,
git-ignored ``.env`` file — via ``pydantic-settings``; nothing is hardcoded in
the application (NFR-MAINT-04). See ``backend/.env.example`` for the documented
variables. Access settings through :func:`get_settings`.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, loaded from the environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Authoritative Postgres store (DESIGN §2, §8.2). Required — the app fails
    # fast at startup if it is absent. PR4 opens the actual connection.
    database_url: str

    # Allowed frontend origins for CORS (DESIGN §3.6/§8). The backend hardcodes
    # no client origin: the Angular app's origin(s) are supplied here. Accepts a
    # comma-separated string; empty means no cross-origin request is allowed.
    cors_allowed_origins: Annotated[list[str], NoDecode] = []

    # Server bind address — consumed by the container / uvicorn invocation (PR6).
    host: str = "0.0.0.0"
    port: int = 8000

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Parse a comma-separated ``CORS_ALLOWED_ORIGINS`` string into a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, instantiated once and cached."""
    # Field values are supplied by the environment / .env at runtime
    # (pydantic-settings), so pyright's "missing argument" for the required
    # fields is a false positive here.
    return Settings()  # pyright: ignore[reportCallIssue]
