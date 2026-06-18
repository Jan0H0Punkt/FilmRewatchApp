"""Tests for the shared strict base schema (DESIGN §5.7, M0 PR3).

Proves the two strictness guarantees every domain schema inherits — unknown
fields rejected, lossy primitive coercion rejected — plus that ISO-8601 strings
still validate for temporal types on the JSON path.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.core.schemas import StrictSchema


class _Sample(StrictSchema):
    count: int


class _Temporal(StrictSchema):
    when: datetime


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _Sample.model_validate({"count": 1, "surprise": 2})


def test_rejects_lossy_coercion() -> None:
    # Strict mode: the string "1" must not be coerced into the int 1.
    with pytest.raises(ValidationError):
        _Sample.model_validate({"count": "1"})


def test_accepts_iso8601_on_json_path() -> None:
    # Strict mode still accepts ISO-8601 strings for datetime via JSON.
    model = _Temporal.model_validate_json('{"when": "2026-06-18T12:00:00"}')
    assert model.when == datetime(2026, 6, 18, 12, 0, 0)
