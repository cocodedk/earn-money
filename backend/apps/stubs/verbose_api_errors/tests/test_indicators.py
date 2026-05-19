"""Tests for stub 1.17 API error indicator matcher.

Spec §"Strong disclosure indicators" — three families:
* JSON debug fields (stack/trace/exception/file/line/...)
* Source path patterns (/app/, /srv/, .py:N, .java:N, ...)
* Database error strings (SQLSTATE, ORA-, PostgreSQL ERROR:, MySQL,
  SQLite, MongoDB exception text)

The indicator matcher returns one ApiErrorIndicator per kind that
fires; the classifier (slice 2) combines them with the response
status into the (confidence, status) verdict.
"""
from __future__ import annotations

import unittest

from ..indicators import ApiErrorIndicator, detect_api_error_indicators


def _kinds(body: str, ct: str = "application/json") -> set[str]:
    return {ind.kind for ind in detect_api_error_indicators(body, ct)}


class JsonDebugFieldTests(unittest.TestCase):
    def test_stack_field_detected(self) -> None:
        body = '{"error": "fail", "stack": "Error at /srv/x.js:1:1"}'
        kinds = _kinds(body)
        assert "json_debug_field" in kinds

    def test_trace_field_detected(self) -> None:
        body = '{"trace": "Traceback ...", "message": "x"}'
        assert "json_debug_field" in _kinds(body)

    def test_exception_field_detected(self) -> None:
        body = '{"exception": "java.lang.NullPointerException"}'
        assert "json_debug_field" in _kinds(body)

    def test_file_line_fields_detected(self) -> None:
        body = '{"file": "/app/main.py", "line": 42}'
        assert "json_debug_field" in _kinds(body)

    def test_traceback_field_detected(self) -> None:
        body = '{"traceback": ["File \\"/x.py\\", line 1, in run"]}'
        assert "json_debug_field" in _kinds(body)

    def test_camelcase_stackTrace_field_detected(self) -> None:
        body = '{"stackTrace": "TypeError: foo"}'
        assert "json_debug_field" in _kinds(body)

    def test_pascalcase_StackTrace_field_detected(self) -> None:
        # .NET DeveloperExceptionPage serialises with PascalCase
        # keys (`StackTrace`, `Source`, `InnerException`). The
        # matcher lowercases keys at walk time so it picks them up.
        body = '{"StackTrace": "System.NullReferenceException..."}'
        assert "json_debug_field" in _kinds(body)

    def test_empty_field_value_skipped(self) -> None:
        # `stack: ""` and `stack: null` mean nothing — must not flag.
        for body in (
            '{"stack": ""}',
            '{"stack": null}',
            '{"trace": []}',
        ):
            assert detect_api_error_indicators(body, "application/json") == []

    def test_generic_message_alone_skipped(self) -> None:
        # Spec lists `message` / `error` / `detail` as WEAK indicators
        # — they're not enough to flag.
        body = '{"error": "not found", "detail": "missing"}'
        assert detect_api_error_indicators(body, "application/json") == []

    def test_non_json_body_with_json_ct_skipped(self) -> None:
        # Malformed JSON: no fields to walk → no field-indicator.
        body = "not json"
        assert detect_api_error_indicators(body, "application/json") == []

    def test_numeric_line_field_alone_is_meaningful(self) -> None:
        # Strong fields can carry numeric values (line numbers).
        # Spec example: `{"file": "/app/x", "line": 42}` — the line
        # field alone qualifies even without a sibling.
        body = '{"line": 42}'
        assert "json_debug_field" in _kinds(body)

    def test_nested_dict_walker(self) -> None:
        # API frameworks often nest the debug payload under an
        # envelope (e.g. {"data": {"file": "/x.py"}}). The walker
        # recurses through dict values.
        body = '{"data": {"file": "/app/x.py"}}'
        assert "json_debug_field" in _kinds(body)

    def test_top_level_array_walker(self) -> None:
        # Some APIs return error lists at the top level.
        body = '[{"file": "/x.py"}, {"unrelated": "field"}]'
        assert "json_debug_field" in _kinds(body)

    def test_array_without_strong_fields_returns_none(self) -> None:
        # Top-level array of plain dicts → walker exits the list
        # loop without finding anything (no flag).
        body = '[{"unrelated": "x"}, {"another": "y"}]'
        assert detect_api_error_indicators(body, "application/json") == []


class SourcePathTests(unittest.TestCase):
    def test_unix_app_path_detected(self) -> None:
        body = "File /app/main.py:42 raised ValueError"
        assert "source_path" in _kinds(body, "text/plain")

    def test_node_modules_detected(self) -> None:
        body = "at handler (/srv/app/node_modules/express/lib/x.js:1:1)"
        assert "source_path" in _kinds(body, "text/plain")

    def test_windows_path_detected(self) -> None:
        body = 'at Acme.Web in "C:\\app\\HomeController.cs:line 42"'
        assert "source_path" in _kinds(body, "text/plain")

    def test_java_line_marker_detected(self) -> None:
        body = "Caused by: at com.example.App.run(App.java:42)"
        assert "source_path" in _kinds(body, "text/plain")


class DatabaseErrorTests(unittest.TestCase):
    def test_sqlstate_detected(self) -> None:
        body = 'ERROR: column "x" does not exist (SQLSTATE 42703)'
        assert "database_error" in _kinds(body, "text/plain")

    def test_oracle_ora_code_detected(self) -> None:
        body = "ORA-00942: table or view does not exist"
        assert "database_error" in _kinds(body, "text/plain")

    def test_postgresql_error_detected(self) -> None:
        body = (
            "psycopg.errors.UndefinedTable: relation \"x\" does not exist"
        )
        assert "database_error" in _kinds(body, "text/plain")

    def test_mysql_error_detected(self) -> None:
        body = "You have an error in your SQL syntax near 'x' at line 1"
        assert "database_error" in _kinds(body, "text/plain")

    def test_sqlite_no_such_table_detected(self) -> None:
        body = "sqlite3.OperationalError: no such table: users"
        assert "database_error" in _kinds(body, "text/plain")

    def test_mssql_error_detected(self) -> None:
        body = "Microsoft SQL Server error: Invalid object name 'x'"
        assert "database_error" in _kinds(body, "text/plain")


class CombinedTests(unittest.TestCase):
    def test_multiple_kinds_surface(self) -> None:
        body = (
            '{"stack": "ORA-00942: missing table",'
            ' "file": "/app/main.py"}'
        )
        kinds = _kinds(body)
        assert "json_debug_field" in kinds
        assert "database_error" in kinds
        assert "source_path" in kinds

    def test_indicator_carries_kind_and_match(self) -> None:
        body = '{"stack": "Error at /srv/x.js:1:1"}'
        result = detect_api_error_indicators(body, "application/json")
        assert all(isinstance(ind, ApiErrorIndicator) for ind in result)
        # Each indicator carries a non-empty matched_value snippet so
        # downstream evidence persistence can excerpt it.
        for ind in result:
            assert ind.matched_value


class EmptyTests(unittest.TestCase):
    def test_empty_body_returns_empty(self) -> None:
        assert detect_api_error_indicators("", "application/json") == []

    def test_no_indicators_returns_empty(self) -> None:
        body = '{"message": "ok"}'
        assert detect_api_error_indicators(body, "application/json") == []
