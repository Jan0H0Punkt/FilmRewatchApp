"""The once-daily rewatch trigger (DESIGN §5.8, §8.1, FR-RW-05).

An in-process asyncio task owned by the app's lifespan, rather than a cron
container beside it: the deployment target is a single laptop running one
container (§1.3), where a scheduler that lives and dies with the app is the
whole requirement — and every start recomputes, so a restart costs nothing.
(OPEN_DECISIONS_V1 "M4 — Scheduler mechanism".)

The cadence is "one interval since the last run", not a wall-clock time of day.
The §5.8 contract only asks for once-daily, and an interval sleep needs no
timezone reasoning.

This module is infrastructure. The algorithm and the service stay unaware of it.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from datetime import date

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.db import session_scope
from app.rewatch.repository import RewatchRepository
from app.rewatch.service import RewatchService

_logger = logging.getLogger(__name__)


def _recompute() -> None:
    """One run against its own session — the unit the loop repeats."""
    with session_scope() as session:
        count = RewatchService(RewatchRepository(session)).recompute(date.today())
    _logger.info("rewatch recompute stored %d due films", count)


def recompute_once() -> None:
    """Run the recompute, swallowing and logging any failure.

    A raising run must not kill the loop: a dead scheduler would freeze the
    due-list at whatever the last successful run produced, silently and
    forever. The previous projection survives untouched (``replace_all`` and
    the insert share one transaction), which is also what FR-RW-07 wants — the
    client keeps showing the last good list.
    """
    try:
        _recompute()
    except Exception:
        _logger.exception("rewatch recompute failed; keeping the previous projection")


async def _run_forever(interval_seconds: int) -> None:
    """Recompute at startup, then once per interval."""
    while True:
        # The recompute is blocking DB work; off the event loop it goes, so a
        # run never stalls the requests the same process is serving.
        await asyncio.to_thread(recompute_once)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Start the daily task with the app and cancel it on shutdown."""
    task = asyncio.create_task(_run_forever(get_settings().rewatch_recompute_interval_seconds))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
