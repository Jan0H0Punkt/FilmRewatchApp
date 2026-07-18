"""Tests for the settings-cache isolation fixture (REVIEW_M0 §7.4, M1 PR2).

``get_settings()`` is ``lru_cache``d; a test overriding the environment must
request ``clear_settings_cache`` to actually see its override — and must not
leak it into later tests. The two tests below prove both halves and pass in
either order (per-test isolation, §9).
"""

import pytest

from app.core.config import get_settings

_SENTINEL_ORIGIN = "http://settings-cache-probe.invalid"


@pytest.mark.usefixtures("clear_settings_cache")
def test_override_is_visible_when_cache_is_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", _SENTINEL_ORIGIN)
    assert get_settings().cors_allowed_origins == [_SENTINEL_ORIGIN]


def test_override_does_not_leak_into_other_tests() -> None:
    assert _SENTINEL_ORIGIN not in get_settings().cors_allowed_origins
