"""Tests for the shared strict base schema (DESIGN §5.7, M0 PR3).

Proves the strictness guarantees every domain schema inherits — unknown fields
rejected, lossy primitive coercion rejected — and that the wire-format aliases
accept ISO-8601 strings on Pydantic's **Python** validation path, which is the
path FastAPI uses for request bodies (it parses the JSON to a ``dict``, then
calls ``validate_python``). The tests deliberately use ``model_validate`` (the
Python path), not ``model_validate_json``, so they reflect real HTTP validation.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.core.schemas import JsonDateTime, StrictSchema


class _Sample(StrictSchema):
    count: int


class _BareTemporal(StrictSchema):
    when: datetime


class _Temporal(StrictSchema):
    when: JsonDateTime


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _Sample.model_validate({"count": 1, "surprise": 2})


def test_rejects_lossy_coercion() -> None:
    # Strict mode: the string "1" must not be coerced into the int 1.
    with pytest.raises(ValidationError):
        _Sample.model_validate({"count": "1"})


def test_bare_temporal_rejects_iso8601_on_python_path() -> None:
    # Guards the trap: a bare `datetime` under strict mode rejects ISO strings on
    # the Python path FastAPI uses — which is why JsonDateTime exists.
    with pytest.raises(ValidationError):
        _BareTemporal.model_validate({"when": "2026-06-18T12:00:00"})


def test_alias_accepts_iso8601_on_python_path() -> None:
    # JsonDateTime accepts the ISO-8601 string exactly as a real request body does.
    model = _Temporal.model_validate({"when": "2026-06-18T12:00:00"})
    assert model.when == datetime(2026, 6, 18, 12, 0, 0)
