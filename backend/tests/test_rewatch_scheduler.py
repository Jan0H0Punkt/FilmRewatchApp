"""The daily recompute trigger (DESIGN §5.8, §8.1) — offline.

What matters here is the *wiring*, not the arithmetic: that the app starts and
stops the task cleanly, that a failing run cannot take the loop or the app
down, and that the interval is configurable.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.rewatch import scheduler


def test_a_failing_run_is_swallowed_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # A run that raises must leave the previous projection in place and let the
    # loop live — a dead scheduler would silently freeze the due-list forever.
    def explode() -> None:
        raise RuntimeError("database is down")

    monkeypatch.setattr(scheduler, "_recompute", explode)

    scheduler.recompute_once()

    assert "rewatch recompute failed" in caplog.text


def test_the_app_starts_the_task_and_cancels_it_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs: list[int] = []
    monkeypatch.setattr(scheduler, "recompute_once", lambda: runs.append(1))

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health").status_code == 200
        # ``create_task`` only schedules; without waiting, shutdown can cancel
        # the task before it reaches its first run and the assertion below
        # would flake. Poll rather than sleep a fixed time, so the common case
        # costs a few milliseconds.
        deadline = time.monotonic() + 2
        while not runs and time.monotonic() < deadline:
            time.sleep(0.01)

    # One run at startup (the loop then sleeps until the next interval).
    assert runs == [1]


def test_the_interval_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REWATCH_RECOMPUTE_INTERVAL_SECONDS", "60")
    get_settings.cache_clear()
    try:
        assert get_settings().rewatch_recompute_interval_seconds == 60
    finally:
        get_settings.cache_clear()


def test_the_interval_defaults_to_one_day() -> None:
    assert get_settings().rewatch_recompute_interval_seconds == 86_400
