"""Presentation layer for the rewatch module (DESIGN §5.1, §5.8).

Serves the daily-computed due-list at ``/api/v1/rewatch-suggestions``. This stub
creates the router; the app factory mounts it. The endpoint (and the pure
algorithm + daily scheduler behind it) arrive in M4.
"""

from fastapi import APIRouter

router = APIRouter()
