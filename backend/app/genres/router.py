"""Presentation layer for the genres module (DESIGN §5.1).

FastAPI routes under ``/api/v1/genres/*``. This stub only creates the module
router; the app factory (``app/main.py``) mounts it. No routes yet — endpoints
arrive in M1+ (§5.3).
"""

from fastapi import APIRouter

router = APIRouter()
