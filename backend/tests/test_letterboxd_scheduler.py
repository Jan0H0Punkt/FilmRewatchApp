"""The background loop's timing and failure handling (offline)."""

import asyncio

import pytest

from app.letterboxd import scheduler
from app.letterboxd.errors import LetterboxdUnavailableError


def test_syncs_at_start_retries_a_failure_then_waits_a_day(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    outcomes: list[int | Exception] = [LetterboxdUnavailableError(), 3]

    def fake_sync(username: str) -> int:
        calls.append(username)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    sleeps = 0

    async def fake_sleep(_seconds: float) -> None:
        nonlocal sleeps
        sleeps += 1
        if sleeps == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(scheduler, "sync_once", fake_sync)
    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_periodically("janhy"))

    # Check 1 fails, check 2 retries and succeeds, check 3 is within 24 h.
    assert calls == ["janhy", "janhy"]
