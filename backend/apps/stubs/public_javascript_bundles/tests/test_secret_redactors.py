"""Tests for stub 1.15 secret redactors.

Spec §4 'Secret handling' + §Safety:
* Do not persist full token-looking values.
* Store only: indicator type, redacted preview, length, hash.

The extractor scans the bundle body for high-signal token shapes
and returns ``TokenIndicator`` records with the raw value REDACTED.
"""
from __future__ import annotations

import hashlib
import unittest

from ..secret_redactors import (
    TokenIndicator,
    extract_token_indicators,
)


_FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJ4eXoiLCJpYXQiOjE2MDB9"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)


def _find(body: str, kind: str) -> TokenIndicator:
    matches = [t for t in extract_token_indicators(body) if t.kind == kind]
    assert matches, f"no {kind} indicator found in body"
    return matches[0]


class JwtTests(unittest.TestCase):
    def test_jwt_detected(self) -> None:
        body = f'var TOKEN = "{_FAKE_JWT}";'
        indicator = _find(body, "jwt")
        assert indicator.length == len(_FAKE_JWT)

    def test_jwt_value_not_in_indicator(self) -> None:
        # Spec §Safety: "Do not persist full token-looking values."
        # The indicator must not carry the raw value in any field.
        body = f'JWT = "{_FAKE_JWT}";'
        indicator = _find(body, "jwt")
        assert _FAKE_JWT not in indicator.redacted_preview
        assert _FAKE_JWT not in indicator.sha256

    def test_jwt_hash_is_sha256_of_raw(self) -> None:
        body = f'"{_FAKE_JWT}"'
        indicator = _find(body, "jwt")
        expected = hashlib.sha256(_FAKE_JWT.encode("utf-8")).hexdigest()
        assert indicator.sha256 == expected

    def test_jwt_preview_shows_short_prefix_only(self) -> None:
        body = f'"{_FAKE_JWT}"'
        indicator = _find(body, "jwt")
        # First 4 chars of the JWT header are public anyway (eyJh).
        assert indicator.redacted_preview.startswith("eyJh")
        assert "*" in indicator.redacted_preview

    def test_non_jwt_three_dot_string_not_flagged(self) -> None:
        # `1.2.3.4` is an IP, not a JWT — the eyJ anchor blocks
        # the false positive.
        assert extract_token_indicators("var ip = '1.2.3.4';") == []


class AwsAccessKeyTests(unittest.TestCase):
    def test_aws_key_detected(self) -> None:
        body = 'const k = "AKIAIOSFODNN7EXAMPLE";'
        indicator = _find(body, "aws_access_key")
        assert indicator.length == 20

    def test_aws_key_redacted(self) -> None:
        body = '"AKIAIOSFODNN7EXAMPLE"'
        indicator = _find(body, "aws_access_key")
        assert "AKIAIOSFODNN7EXAMPLE" not in indicator.redacted_preview
        # The AKIA prefix is itself the indicator class signal —
        # keeping it in the preview is informative without leaking.
        assert indicator.redacted_preview.startswith("AKIA")

    def test_short_string_starting_AKIA_not_flagged(self) -> None:
        # AKIA requires exactly 16 more A-Z0-9 chars to qualify; a
        # shorter "AKIA123" must not be a false positive.
        assert extract_token_indicators('var x = "AKIA123";') == []


class UrlWithCredentialsTests(unittest.TestCase):
    def test_credentials_in_url_detected(self) -> None:
        body = 'var DB = "https://admin:p@ss@db.internal/x";'
        indicator = _find(body, "url_with_credentials")
        assert "admin:p@ss" not in indicator.redacted_preview

    def test_plain_url_not_flagged(self) -> None:
        body = 'fetch("https://api.example.com/v1")'
        assert extract_token_indicators(body) == []

    def test_http_with_creds_also_detected(self) -> None:
        # The scheme parity is intentional — http-with-creds is the
        # more dangerous of the two (no TLS).
        body = '"http://user:pw@host.local/api"'
        assert any(
            t.kind == "url_with_credentials"
            for t in extract_token_indicators(body)
        )


class BearerTokenTests(unittest.TestCase):
    def test_bearer_token_detected(self) -> None:
        body = (
            'headers={"Authorization":'
            ' "Bearer abc123def456ghi789jkl012mno345"};'
        )
        indicator = _find(body, "bearer_token")
        assert indicator.length >= 30
        assert "abc123def456" not in indicator.redacted_preview

    def test_short_bearer_not_flagged(self) -> None:
        # Need at least 20 chars to look like a real token; the
        # word "Bearer x" must not flag.
        body = '"Bearer x"'
        assert extract_token_indicators(body) == []


class GeneralTests(unittest.TestCase):
    def test_empty_body_returns_empty(self) -> None:
        assert extract_token_indicators("") == []

    def test_no_tokens_returns_empty(self) -> None:
        assert extract_token_indicators("var x = 1;") == []

    def test_multiple_token_kinds(self) -> None:
        body = (
            f'JWT="{_FAKE_JWT}";'
            'KEY="AKIAIOSFODNN7EXAMPLE";'
            'DB="https://u:p@host/x";'
        )
        kinds = {t.kind for t in extract_token_indicators(body)}
        assert kinds == {"jwt", "aws_access_key", "url_with_credentials"}

    def test_dedupes_same_value(self) -> None:
        # The same JWT pasted twice in a bundle (e.g. a vendor chunk
        # and a manifest reference) should land as ONE indicator.
        body = f'"{_FAKE_JWT}"; "{_FAKE_JWT}"'
        jwt_indicators = [
            t for t in extract_token_indicators(body) if t.kind == "jwt"
        ]
        assert len(jwt_indicators) == 1

    def test_returns_namedtuple(self) -> None:
        body = f'"{_FAKE_JWT}"'
        indicator = _find(body, "jwt")
        assert isinstance(indicator, TokenIndicator)
