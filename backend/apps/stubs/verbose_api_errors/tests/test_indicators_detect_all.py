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
    scrubbed of secrets before they flow into Finding.data —
    across ALL indicator kinds (json_debug_field, source_path,
    database_error), not just JSON debug fields."""

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


class RedactedDatabaseErrorTests(unittest.TestCase):
    """DB driver errors can span their captured content widely —
    MSSQL's `Microsoft SQL Server ... error` regex consumes up to
    200 chars between the anchors. If a password lands inside that
    span, the matched_value must scrub it before persistence."""

    def test_password_inside_mssql_span_redacted(self) -> None:
        body = (
            "Microsoft SQL Server failed connection with "
            "password=hunter2supersecret reason error: invalid creds"
        )
        result = detect_api_error_indicators(body, "text/plain")
        db = next(i for i in result if i.kind == "database_error")
        assert "hunter2supersecret" not in db.matched_value
        assert "[REDACTED:secret]" in db.matched_value

    def test_password_in_mssql_span_detect_all(self) -> None:
        body = (
            "Microsoft SQL Server failed connection with "
            "password=anothersecretvalue reason error: invalid creds"
        )
        result = detect_all_indicators(body, "text/plain")
        db = next(i for i in result if i.kind == "database_error")
        assert "anothersecretvalue" not in db.matched_value


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
