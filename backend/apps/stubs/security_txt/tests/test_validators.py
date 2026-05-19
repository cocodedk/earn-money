"""Pure-function tests for stub 1.13 validators.

Spec §Detection logic Validation rules: Contact URI shape + scheme,
Expires RFC3339 parse + freshness, Canonical absolute-URL shape +
URL matching.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ..validators import (
    is_canonical_match,
    is_expired,
    is_valid_contact,
    is_valid_uri,
    parse_expires,
)


_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


class ContactValidationTests(unittest.TestCase):
    def test_mailto_is_valid(self) -> None:
        assert is_valid_contact("mailto:security@example.test") is True

    def test_https_is_valid(self) -> None:
        assert is_valid_contact("https://example.test/report") is True

    def test_http_is_valid(self) -> None:
        # http is allowed per spec but should produce a warning at
        # the classifier layer — the validator only checks shape.
        assert is_valid_contact("http://example.test/report") is True

    def test_tel_is_valid(self) -> None:
        assert is_valid_contact("tel:+15551234567") is True

    def test_unsupported_scheme_invalid(self) -> None:
        assert is_valid_contact("ftp://example.test/x") is False

    def test_no_scheme_invalid(self) -> None:
        assert is_valid_contact("security@example.test") is False

    def test_empty_string_invalid(self) -> None:
        assert is_valid_contact("") is False


class ExpiresParseTests(unittest.TestCase):
    def test_z_suffix_parsed(self) -> None:
        result = parse_expires("2027-01-01T00:00:00Z")
        assert result is not None
        assert result.year == 2027

    def test_offset_suffix_parsed(self) -> None:
        result = parse_expires("2027-01-01T00:00:00+02:00")
        assert result is not None

    def test_malformed_returns_none(self) -> None:
        assert parse_expires("not a date") is None

    def test_empty_returns_none(self) -> None:
        assert parse_expires("") is None

    def test_date_only_returns_none(self) -> None:
        # Spec says RFC3339/ISO-8601 *timestamp* — bare date isn't
        # enough for an expiry value.
        assert parse_expires("2027-01-01") is None


class ExpiredTests(unittest.TestCase):
    def test_past_value_is_expired(self) -> None:
        assert is_expired("2020-01-01T00:00:00Z", now=_NOW) is True

    def test_future_value_not_expired(self) -> None:
        assert is_expired("2030-01-01T00:00:00Z", now=_NOW) is False

    def test_malformed_value_treated_as_not_expired(self) -> None:
        # Malformed dates trigger a separate finding
        # (malformed_security_txt); is_expired returns False so the
        # caller can distinguish "no expiry data" from "data says
        # expired".
        assert is_expired("not a date", now=_NOW) is False


class CanonicalMatchTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        assert is_canonical_match(
            "https://example.test/.well-known/security.txt",
            final_url="https://example.test/.well-known/security.txt",
        ) is True

    def test_different_host_no_match(self) -> None:
        assert is_canonical_match(
            "https://other.example/.well-known/security.txt",
            final_url="https://example.test/.well-known/security.txt",
        ) is False

    def test_different_path_no_match(self) -> None:
        assert is_canonical_match(
            "https://example.test/security.txt",
            final_url="https://example.test/.well-known/security.txt",
        ) is False

    def test_trailing_slash_tolerated(self) -> None:
        # Some servers add or strip the trailing slash on redirect.
        # Treat as a match — the path stems are identical.
        assert is_canonical_match(
            "https://example.test/.well-known/security.txt",
            final_url="https://example.test/.well-known/security.txt/",
        ) is True


class UriShapeTests(unittest.TestCase):
    def test_https_is_valid_uri(self) -> None:
        assert is_valid_uri("https://example.test/policy") is True

    def test_relative_path_not_valid_uri(self) -> None:
        # URL-valued fields require absolute URLs.
        assert is_valid_uri("/policy") is False

    def test_empty_not_valid_uri(self) -> None:
        assert is_valid_uri("") is False

    def test_malformed_not_valid_uri(self) -> None:
        assert is_valid_uri("not a url") is False
