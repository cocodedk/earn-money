"""Tests for stub 1.17 indicators — detect_all_indicators path +
FU-1 matched_value redaction."""
from __future__ import annotations

import unittest

from ..indicators import (
    detect_all_indicators,
    detect_api_error_indicators,
)


class RedactedMatchedValueTests(unittest.TestCase):
    """FU-1: matched_value snippets stored on indicators must be
    scrubbed of secrets before they flow into Finding.data."""

    def test_jwt_in_json_field_redacted(self) -> None:
        body = (
            '{"stack": "Error decoding token '
            'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signedpart"}'
        )
        result = detect_api_error_indicators(body, "application/json")
        snippet = next(
            i.matched_value for i in result if i.kind == "json_debug_field"
        )
        assert "eyJhbGciOiJIUzI1NiJ9" not in snippet
        assert "[REDACTED:jwt]" in snippet

    def test_email_in_json_field_redacted(self) -> None:
        body = '{"exception": "User alice@example.com not found"}'
        result = detect_api_error_indicators(body, "application/json")
        snippet = next(
            i.matched_value for i in result if i.kind == "json_debug_field"
        )
        assert "alice@example.com" not in snippet
        assert "[REDACTED:email]" in snippet


class DetectAllIndicatorsTests(unittest.TestCase):
    """detect_all_indicators(...) is the broader variant — the
    signature builder uses it to populate plural hint arrays per
    spec §"Persistence"."""

    def test_empty_body_returns_empty(self) -> None:
        assert detect_all_indicators("", "application/json") == []

    def test_collects_all_database_matches(self) -> None:
        body = (
            "ORA-00942: missing table\n"
            "sqlite3.OperationalError: no such table: x"
        )
        result = detect_all_indicators(body, "text/plain")
        db_values = {i.matched_value for i in result if i.kind == "database_error"}
        assert len(db_values) >= 2

    def test_collects_all_source_paths(self) -> None:
        body = "Stack:\n  /app/main.py:42\n  /srv/handler.py:5\n"
        result = detect_all_indicators(body, "text/plain")
        paths = {i.matched_value for i in result if i.kind == "source_path"}
        assert "/app/main.py:42" in paths
        assert "/srv/handler.py:5" in paths

    def test_collects_all_json_fields(self) -> None:
        body = '{"stack": "x", "exception": "ValueError", "file": "/a"}'
        result = detect_all_indicators(body, "application/json")
        json_count = sum(1 for i in result if i.kind == "json_debug_field")
        assert json_count == 3
