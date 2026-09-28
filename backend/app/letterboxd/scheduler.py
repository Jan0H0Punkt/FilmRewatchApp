"""The background Letterboxd sync (FR-LBX-01), started by the app lifespan when a username is set.

Checks hourly against the wall clock rather than sleeping 24 h, so a laptop
that slept through the night still syncs the morning after.
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

from app.core.db import session_scope
from app.letterboxd.feed import fetch_feed
from app.letterboxd.repository import LetterboxdRepository
from app.letterboxd.service import run_sync

CHECK_INTERVAL = timedelta(hours=1)
SYNC_INTERVAL = timedelta(hours=24)

logger = logging.getLogger(__name__)


def sync_once(username: str) -> int:
    """One sync in its own session; returns how many entries were queued."""
    with session_scope() as session:
        return run_sync(LetterboxdRepository(session), fetch_feed(username), date.today())


async def run_periodically(username: str) -> None:
    """Sync now, then whenever the last success is a day old; failures retry at the next check."""
    last_synced: datetime | None = None
    while True:
        now = datetime.now(UTC)
        if last_synced is None or now - last_synced >= SYNC_INTERVAL:
            try:
                queued = await asyncio.to_thread(sync_once, username)
            except Exception:
                logger.warning("Letterboxd sync failed, retrying in an hour", exc_info=True)
            else:
                last_synced = now
                logger.info("Letterboxd sync queued %d entries", queued)
        await asyncio.sleep(CHECK_INTERVAL.total_seconds())
