"""Tests for `_shared/auth/_normalize_parse` helpers.

`test_normalize.py` is already over the 200-line cap; new edge cases
for the underlying parse helpers live here.

Covers:
- parse_json_errors when body decodes to a non-dict (line 33)
"""
from __future__ import annotations

from apps.stubs._shared.auth._normalize_parse import parse_json_errors


def test_parse_json_errors_returns_empty_when_body_is_list() -> None:
    """A JSON body that is a list (not a dict) returns (None, {}) —
    there's no 'error_code' or 'errors' key to extract."""
    code, fields = parse_json_errors(
        '[{"error": "bad"}]',
        "application/json",
    )
    assert code is None
    assert fields == {}


def test_parse_json_errors_returns_empty_when_body_is_string() -> None:
    """A JSON body that is a bare string (not a dict) also returns
    (None, {})."""
    code, fields = parse_json_errors('"just a string"', "application/json")
    assert code is None
    assert fields == {}


def test_parse_json_errors_returns_empty_when_body_is_number() -> None:
    """A JSON body that is a number (not a dict) returns (None, {})."""
    code, fields = parse_json_errors("42", "application/json")
    assert code is None
    assert fields == {}
