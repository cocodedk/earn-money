"""Tests for the stub 1.2 header matcher.

The matcher operates on a `headers` dict (case-preserving but matched
case-insensitively per RFC 7230 §3.2). The matcher returns the matched
signatures; version extraction is a separate step on each matched
signature.
"""
from __future__ import annotations

import unittest

from ..matcher import extract_version, match_signatures, normalize_headers


SIG_NGINX = {
    "id": "server_nginx",
    "header_name": "server",
    "value_pattern": "nginx",
    "match_type": "contains",
    "technology": "nginx",
    "technology_category": "web_server",
    "version_regex": r"nginx/([0-9.]+)",
    "confidence": "high",
}
SIG_CLOUDFLARE_RAY = {
    "id": "cloudflare_cf_ray",
    "header_name": "cf-ray",
    "value_pattern": ".+",
    "match_type": "regex",
    "technology": "cloudflare",
    "technology_category": "cdn",
    "version_regex": None,
    "confidence": "high",
}
SIG_EXACT = {
    "id": "iis",
    "header_name": "server",
    "value_pattern": "Microsoft-IIS/10.0",
    "match_type": "exact",
    "technology": "iis",
    "technology_category": "web_server",
    "version_regex": r"Microsoft-IIS/([0-9.]+)",
    "confidence": "high",
}


class NormalizeHeadersTests(unittest.TestCase):
    def test_keys_lowercased(self) -> None:
        norm = normalize_headers({"Server": "nginx", "X-Powered-By": "Express"})
        assert norm == {"server": "nginx", "x-powered-by": "Express"}

    def test_values_preserved(self) -> None:
        norm = normalize_headers({"Server": "nginx/1.24.0"})
        assert norm["server"] == "nginx/1.24.0"

    def test_empty_input(self) -> None:
        assert normalize_headers({}) == {}


class ContainsMatcherTests(unittest.TestCase):
    def test_contains_match_case_insensitive_value(self) -> None:
        hits = match_signatures([SIG_NGINX], {"server": "NGINX/1.24.0"})
        assert hits == [SIG_NGINX]

    def test_no_match_when_header_absent(self) -> None:
        assert match_signatures([SIG_NGINX], {"x-other": "nginx"}) == []

    def test_no_match_when_value_differs(self) -> None:
        assert match_signatures([SIG_NGINX], {"server": "apache"}) == []


class RegexMatcherTests(unittest.TestCase):
    def test_regex_match_on_any_value(self) -> None:
        hits = match_signatures(
            [SIG_CLOUDFLARE_RAY], {"cf-ray": "76abc-CDG"}
        )
        assert hits == [SIG_CLOUDFLARE_RAY]

    def test_regex_no_match_when_value_empty(self) -> None:
        # `.+` requires at least one character.
        assert match_signatures([SIG_CLOUDFLARE_RAY], {"cf-ray": ""}) == []


class ExactMatcherTests(unittest.TestCase):
    def test_exact_matches_full_value(self) -> None:
        hits = match_signatures(
            [SIG_EXACT], {"server": "Microsoft-IIS/10.0"}
        )
        assert hits == [SIG_EXACT]

    def test_exact_rejects_substring_only(self) -> None:
        assert match_signatures(
            [SIG_EXACT], {"server": "Microsoft-IIS/10.0-customized"}
        ) == []


class ExtractVersionTests(unittest.TestCase):
    """`extract_version` takes already-normalized headers (caller calls
    `normalize_headers` once for the whole match-then-extract pass)."""

    def test_extracts_when_pattern_matches(self) -> None:
        assert (
            extract_version(
                SIG_NGINX,
                normalize_headers({"Server": "nginx/1.24.0"}),
            )
            == "1.24.0"
        )

    def test_returns_none_when_signature_has_no_version_regex(self) -> None:
        assert extract_version(SIG_CLOUDFLARE_RAY, {"cf-ray": "x"}) is None

    def test_returns_none_when_regex_does_not_match(self) -> None:
        assert extract_version(SIG_NGINX, {"server": "nginx"}) is None

    def test_handles_missing_header(self) -> None:
        assert extract_version(SIG_NGINX, {}) is None
