"""Shared environment for the backend test suite.

Building the FastAPI app (``create_app``) loads settings, which require
``DATABASE_URL`` (DESIGN §3.5). Tests never open a connection — the engine is
created lazily on first use — so a placeholder URL is enough to construct the
app offline. ``setdefault`` leaves a real value from the environment intact.
"""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test"
)
