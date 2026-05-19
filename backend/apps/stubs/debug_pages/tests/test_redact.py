"""Tests for stub 1.10 secret-redaction helpers.

Spec §Safety: "Redact secret-like values before writing snippets" —
API keys, bearer tokens, passwords, db URLs, cloud credentials. Tests
pin redaction at the snippet-construction step, NOT at the response-
read step (raw bodies still pass through the in-memory bundle for
classification; only the persisted excerpt is redacted).
"""
from __future__ import annotations

import unittest

from ..redact import redact_secrets


class EnvVarAssignmentTests(unittest.TestCase):
    def test_secret_key_assignment_value_replaced(self) -> None:
        out = redact_secrets("SECRET_KEY=super-secret-value-here")
        assert "super-secret-value-here" not in out
        assert "SECRET_KEY=" in out
        assert "<REDACTED>" in out

    def test_database_url_password_replaced(self) -> None:
        out = redact_secrets(
            "DATABASE_URL=postgres://app:hunter2@db.local:5432/x"
        )
        assert "hunter2" not in out
        assert "DATABASE_URL=" in out

    def test_aws_access_key_replaced(self) -> None:
        out = redact_secrets("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE")
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        assert "AWS_ACCESS_KEY_ID=" in out

    def test_password_assignment_replaced(self) -> None:
        out = redact_secrets("DB_PASSWORD=hunter2-the-second")
        assert "hunter2-the-second" not in out
        assert "DB_PASSWORD=" in out

    def test_non_secret_env_var_kept(self) -> None:
        # NODE_ENV=development is metadata, not a secret. Don't redact.
        out = redact_secrets("NODE_ENV=development")
        assert "development" in out
        assert "<REDACTED>" not in out

    def test_case_insensitive_key_matching(self) -> None:
        # Lowercase keys appear in JSON config dumps; the redactor
        # must match the spec's secret_like_value class regardless
        # of case.
        out = redact_secrets("secret_key=lower-case-value")
        assert "lower-case-value" not in out


class JsonValueTests(unittest.TestCase):
    def test_json_secret_key_quoted_value_replaced(self) -> None:
        out = redact_secrets('{"secret_key": "json-shaped-secret"}')
        assert "json-shaped-secret" not in out
        assert '"secret_key"' in out

    def test_json_password_value_replaced(self) -> None:
        out = redact_secrets('{"password": "p4ssw0rd"}')
        assert "p4ssw0rd" not in out


class StandaloneTokenTests(unittest.TestCase):
    def test_aws_access_key_id_inline_replaced(self) -> None:
        # AKIA-prefix keys are recognisable even when not paired with
        # a key=value or json key — spec §"AWS_ACCESS_KEY_ID" markers.
        out = redact_secrets("token: AKIAIOSFODNN7EXAMPLE in trace")
        assert "AKIAIOSFODNN7EXAMPLE" not in out


class EmptyAndIdempotenceTests(unittest.TestCase):
    def test_empty_snippet_unchanged(self) -> None:
        assert redact_secrets("") == ""

    def test_no_secret_unchanged(self) -> None:
        snippet = "<h1>Apache Server Status</h1>\nServerVersion is hidden"
        assert redact_secrets(snippet) == snippet

    def test_idempotent_when_run_twice(self) -> None:
        first = redact_secrets("SECRET_KEY=value1\nDB_PASSWORD=value2")
        second = redact_secrets(first)
        assert first == second
