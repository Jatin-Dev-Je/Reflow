"""Result type sanity checks."""

from __future__ import annotations

import pytest

from reflow.core.types import Err, Ok

pytestmark = pytest.mark.unit


def test_ok_carries_value() -> None:
    r = Ok(42)
    assert r.is_ok
    assert not r.is_err
    assert r.value == 42


def test_err_carries_error() -> None:
    r = Err("boom")
    assert not r.is_ok
    assert r.is_err
    assert r.error == "boom"


def test_ok_and_err_are_distinct_types() -> None:
    assert isinstance(Ok(1), Ok)
    assert not isinstance(Err("x"), Ok)
