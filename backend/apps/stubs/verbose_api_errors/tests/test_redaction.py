"""Tests for stub 1.17 FU-1 redaction helper.

Spec §Safety + §config `redact_secrets=true`: matched body snippets
and Evidence body excerpts must scrub tokens, keys, credentials,
and PII before persistence. The redactor replaces matched substrings
with `[REDACTED:<kind>]` so the kind is preserved without the value.
"""
from __future__ import annotations

import unittest

from ..redaction import redact


class JwtRedactionTests(unittest.TestCase):
    def test_jwt_in_body_is_redacted(self) -> None:
        body = (
            'Authorization failed: eyJhbGciOiJIUzI1NiJ9'
            '.eyJzdWIiOiIxMjM0NSJ9.signature123'
        )
        out = redact(body)
        assert "[REDACTED:jwt]" in out
        assert "eyJ" not in out
        assert "signature123" not in out

    def test_jwt_only_redacts_three_segment_base64(self) -> None:
        # Two-segment "eyJ" must NOT trigger — JWTs are always 3-part.
        body = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9'
        out = redact(body)
        assert "eyJhbGciOiJIUzI1NiJ9" in out


class BearerTokenTests(unittest.TestCase):
    def test_bearer_token_redacted(self) -> None:
        body = 'curl -H "Authorization: Bearer abc.def.ghi-xyz_123"'
        out = redact(body)
        assert "[REDACTED:bearer]" in out
        assert "abc.def.ghi-xyz_123" not in out

    def test_bearer_keyword_preserved(self) -> None:
        # The literal "Bearer " label is fine to keep; only the
        # token value is sensitive.
        body = "Authorization: Bearer secrettoken123"
        out = redact(body)
        assert "[REDACTED:bearer]" in out


class ApiKeyTests(unittest.TestCase):
    def test_stripe_secret_key_redacted(self) -> None:
        body = "stripe_key=sk_live_abc123XYZdef456GHIjkl"
        out = redact(body)
        assert "sk_live_abc123XYZdef456GHIjkl" not in out
        assert "[REDACTED:api_key]" in out

    def test_github_pat_redacted(self) -> None:
        body = "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789AB"
        out = redact(body)
        assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789AB" not in out
        assert "[REDACTED:api_key]" in out

    def test_aws_access_key_redacted(self) -> None:
        body = "AWS_KEY=AKIAIOSFODNN7EXAMPLE used here"
        out = redact(body)
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        assert "[REDACTED:api_key]" in out

    def test_slack_token_redacted(self) -> None:
        body = "slack=xoxb-1234567890-abcdef-ghijkl"
        out = redact(body)
        assert "xoxb-1234567890-abcdef-ghijkl" not in out
        assert "[REDACTED:api_key]" in out


class EmailRedactionTests(unittest.TestCase):
    def test_email_redacted(self) -> None:
        body = "user contact: alice.smith@example.com is the owner"
        out = redact(body)
        assert "alice.smith@example.com" not in out
        assert "[REDACTED:email]" in out

    def test_plain_word_with_at_not_redacted(self) -> None:
        # "@param" / "@returns" docstring shapes must not trigger.
        body = "@param x @returns y"
        out = redact(body)
        assert "@param" in out and "@returns" in out


class UrlWithCredentialsTests(unittest.TestCase):
    def test_basic_auth_url_redacted(self) -> None:
        body = "db_url=https://admin:p4ssw0rd@db.internal/scanner"
        out = redact(body)
        assert "admin:p4ssw0rd" not in out
        assert "[REDACTED:url_creds]" in out


class GenericKeyValueTests(unittest.TestCase):
    def test_password_kv_redacted(self) -> None:
        body = 'password="hunter2supersecret"'
        out = redact(body)
        assert "hunter2supersecret" not in out
        assert "[REDACTED:secret]" in out

    def test_api_key_kv_redacted(self) -> None:
        body = "api_key=abcdef0123456789ABCDEF"
        out = redact(body)
        assert "abcdef0123456789ABCDEF" not in out
        assert "[REDACTED" in out


class IdempotenceTests(unittest.TestCase):
    def test_redact_is_idempotent(self) -> None:
        # Running redact twice produces the same output.
        body = "Bearer eyJh.eyJz.sig and password=secret123long"
        first = redact(body)
        second = redact(first)
        assert first == second

    def test_empty_body_returns_empty(self) -> None:
        assert redact("") == ""

    def test_body_without_secrets_unchanged(self) -> None:
        body = "404 Not Found"
        assert redact(body) == body


class CombinedTests(unittest.TestCase):
    def test_multiple_secret_kinds_in_one_body(self) -> None:
        body = (
            "user@example.com logged in with Bearer abc.def.ghi-jkl; "
            "stripe=sk_live_aaaabbbbccccddddeeee; password=hunter2long"
        )
        out = redact(body)
        for value in (
            "user@example.com",
            "abc.def.ghi-jkl",
            "sk_live_aaaabbbbccccddddeeee",
            "hunter2long",
        ):
            assert value not in out
