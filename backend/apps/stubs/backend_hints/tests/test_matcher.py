"""Matcher tests for stub 1.4 backend-hints.

The matcher operates on an EvidenceBundle:
  {
    "probes": {
      "<path>": {
        "headers": dict[str, str],  # lowercased keys
        "cookies": list[str],        # cookie names (values redacted)
        "body": str,
      },
      ...
    },
  }
"""
from __future__ import annotations

import unittest

from ..matcher import extract_version, match_signatures


def _bundle(probes: dict[str, dict] | None = None) -> dict:
    return {"probes": probes or {}}


def _probe(
    headers: dict[str, str] | None = None,
    cookies: list[str] | None = None,
    body: str = "",
) -> dict:
    return {
        "headers": headers or {},
        "cookies": cookies or [],
        "body": body,
    }


SIG_COOKIE_CONNECT_SID = {
    "id": "cookie_connect_sid_express",
    "technology": "Express",
    "category": "app_framework",
    "source": "cookie",
    "match_type": "exact",
    "value_pattern": "connect.sid",
    "version_regex": None,
    "confidence": "high",
}

SIG_HEADER_PHP = {
    "id": "header_powered_by_php",
    "technology": "PHP",
    "category": "app_runtime",
    "source": "header",
    "field": "x-powered-by",
    "match_type": "contains",
    "value_pattern": "PHP",
    "version_regex": r"PHP/([0-9.]+)",
    "confidence": "high",
}

SIG_HEADER_ASPNET_REGEX = {
    "id": "header_aspnet_version",
    "technology": "ASP.NET",
    "category": "app_framework",
    "source": "header",
    "field": "x-aspnet-version",
    "match_type": "regex",
    "value_pattern": r".+",
    "version_regex": r"^([0-9.]+)$",
    "confidence": "high",
}

SIG_BODY_WHITELABEL = {
    "id": "body_whitelabel_error",
    "technology": "Spring Boot",
    "category": "error_page",
    "source": "body",
    "match_type": "contains",
    "value_pattern": "Whitelabel Error Page",
    "version_regex": None,
    "confidence": "high",
}

SIG_COOKIE_ASPNET_CORE_REGEX = {
    "id": "cookie_aspnet_core",
    "technology": "ASP.NET",
    "category": "app_framework",
    "source": "cookie",
    "match_type": "regex",
    "value_pattern": r"^\.AspNetCore\.",
    "version_regex": None,
    "confidence": "high",
}


class CookieMatchTests(unittest.TestCase):
    def test_exact_cookie_name_match(self) -> None:
        bundle = _bundle({"/": _probe(cookies=["connect.sid"])})
        assert match_signatures([SIG_COOKIE_CONNECT_SID], bundle) == [
            SIG_COOKIE_CONNECT_SID
        ]

    def test_no_match_when_cookie_absent(self) -> None:
        bundle = _bundle({"/": _probe(cookies=["other_cookie"])})
        assert match_signatures([SIG_COOKIE_CONNECT_SID], bundle) == []

    def test_regex_cookie_name_match(self) -> None:
        bundle = _bundle({"/": _probe(cookies=[".AspNetCore.Antiforgery"])})
        assert match_signatures([SIG_COOKIE_ASPNET_CORE_REGEX], bundle) == [
            SIG_COOKIE_ASPNET_CORE_REGEX
        ]


class HeaderMatchTests(unittest.TestCase):
    def test_contains_header_value(self) -> None:
        bundle = _bundle({
            "/": _probe(headers={"x-powered-by": "PHP/8.2.0"})
        })
        assert match_signatures([SIG_HEADER_PHP], bundle) == [SIG_HEADER_PHP]

    def test_regex_header_match(self) -> None:
        bundle = _bundle({
            "/": _probe(headers={"x-aspnet-version": "4.0.30319"})
        })
        assert match_signatures(
            [SIG_HEADER_ASPNET_REGEX], bundle
        ) == [SIG_HEADER_ASPNET_REGEX]

    def test_no_match_when_header_absent(self) -> None:
        bundle = _bundle({"/": _probe(headers={"server": "Apache"})})
        assert match_signatures([SIG_HEADER_PHP], bundle) == []


class BodyMatchTests(unittest.TestCase):
    def test_body_pattern_match_on_any_probe(self) -> None:
        # /nonexistent-... 404 body has the Spring Whitelabel marker
        bundle = _bundle({
            "/": _probe(body="welcome"),
            "/__scanner_404_xyz": _probe(
                body="<h1>Whitelabel Error Page</h1>"
            ),
        })
        assert match_signatures([SIG_BODY_WHITELABEL], bundle) == [
            SIG_BODY_WHITELABEL
        ]

    def test_no_match_when_no_probe_body_contains(self) -> None:
        bundle = _bundle({"/": _probe(body="plain index")})
        assert match_signatures([SIG_BODY_WHITELABEL], bundle) == []

    def test_empty_probe_body_yields_no_match(self) -> None:
        # All probes have empty bodies — the generator skips them and
        # the matcher sees zero candidate values.
        bundle = _bundle({"/": _probe(body=""), "/api/": _probe(body="")})
        assert match_signatures([SIG_BODY_WHITELABEL], bundle) == []


class ExtractVersionTests(unittest.TestCase):
    def test_extracts_php_version_from_header(self) -> None:
        bundle = _bundle({
            "/": _probe(headers={"x-powered-by": "PHP/8.2.12"})
        })
        assert extract_version(SIG_HEADER_PHP, bundle) == "8.2.12"

    def test_none_when_no_version_regex(self) -> None:
        bundle = _bundle({"/": _probe(cookies=["connect.sid"])})
        assert extract_version(SIG_COOKIE_CONNECT_SID, bundle) is None

    def test_none_when_regex_misses(self) -> None:
        bundle = _bundle({
            "/": _probe(headers={"x-powered-by": "PHP"})  # no /version
        })
        assert extract_version(SIG_HEADER_PHP, bundle) is None

    def test_none_when_header_absent(self) -> None:
        bundle = _bundle({"/": _probe()})
        assert extract_version(SIG_HEADER_PHP, bundle) is None
