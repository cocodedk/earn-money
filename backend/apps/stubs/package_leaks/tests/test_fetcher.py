"""Fetcher tests for stub 1.5 package-version-leaks.

The fetcher probes a small fixed list of dep-manifest paths. Responses
are classified by content shape — an SPA shell that returns 200 for
every unknown path (Juice Shop's Angular fallthrough is the canonical
case) is filtered out so we don't run JSON parsers on HTML bodies.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from ..fetcher import FetcherConfig, PROBE_PATHS, fetch_evidence


def _resp(
    body: str = "",
    *,
    status_code: int = 200,
    url: str = "https://x.example/",
    content_type: str = "text/plain",
) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status_code,
        headers={"Content-Type": content_type},
        content=body.encode("utf-8"),
        request=req,
    )


def _mock_get(responses: dict[str, httpx.Response]):
    def side_effect(url, **_kwargs):
        if url in responses:
            return responses[url]
        return _resp("", status_code=404, url=url)
    return side_effect


class PathProbeListTests(unittest.TestCase):
    def test_includes_mvp_minimum_paths(self) -> None:
        for path in (
            "/package.json",
            "/composer.json",
            "/requirements.txt",
            "/Gemfile",
            "/pom.xml",
        ):
            assert path in PROBE_PATHS


class SuccessfulProbeTests(unittest.TestCase):
    def test_captures_response_body_and_content_type(self) -> None:
        body = '{"name": "x", "version": "1.0"}'
        responses = {
            "https://x.example/package.json": _resp(
                body, content_type="application/json"
            ),
        }
        with patch(
            "apps.stubs.package_leaks.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        # All probed paths land in the bundle; /package.json has content
        responses_map = bundle["responses"]
        assert "/package.json" in responses_map
        assert responses_map["/package.json"]["body"] == body
        assert responses_map["/package.json"]["content_type"] == "application/json"
        assert responses_map["/package.json"]["status"] == 200


class HtmlShellFilterTests(unittest.TestCase):
    def test_spa_html_response_excluded_from_results(self) -> None:
        # Juice Shop's Angular SPA returns 200 + index.html for every
        # unknown path. We must NOT run the JSON parser on this body.
        html = "<!DOCTYPE html><html><body><app-root></app-root></body></html>"
        responses = {
            "https://x.example/package.json": _resp(
                html, content_type="text/html"
            ),
        }
        with patch(
            "apps.stubs.package_leaks.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        # SPA shells filtered.
        assert "/package.json" not in bundle["responses"]

    def test_doctype_lowercase_also_filtered(self) -> None:
        html = "<!doctype html>\n<html>\n<body>plain</body></html>"
        responses = {
            "https://x.example/composer.json": _resp(html),
        }
        with patch(
            "apps.stubs.package_leaks.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        assert "/composer.json" not in bundle["responses"]


class NotFoundTests(unittest.TestCase):
    def test_404_responses_excluded(self) -> None:
        # All probes return 404 — bundle has zero responses.
        with patch(
            "apps.stubs.package_leaks.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get({})
            bundle = fetch_evidence("https://x.example/")

        assert bundle["responses"] == {}


class NonParseableStatusTests(unittest.TestCase):
    def test_500_response_excluded(self) -> None:
        # 5xx is non-parseable per the spec; runner mustn't see it.
        responses = {
            "https://x.example/package.json": _resp(
                '{"error": "internal"}',
                status_code=500,
                content_type="application/json",
            ),
        }
        with patch(
            "apps.stubs.package_leaks.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        assert "/package.json" not in bundle["responses"]

    def test_401_protected_response_excluded_from_mvp(self) -> None:
        # Spec §Direct path probes calls 401/403 "non-leaking" unless
        # the body itself exposes data. MVP drops them; a follow-up
        # can add a body-of-auth-required signal.
        responses = {
            "https://x.example/composer.json": _resp(
                "auth required",
                status_code=401,
            ),
        }
        with patch(
            "apps.stubs.package_leaks.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        assert "/composer.json" not in bundle["responses"]


class TransportErrorTests(unittest.TestCase):
    def test_per_probe_failure_doesnt_abort_others(self) -> None:
        def side_effect(url, **_kwargs):
            if "/package.json" in url:
                raise httpx.ConnectError("refused")
            if "/composer.json" in url:
                return _resp(
                    '{"name": "ok"}', content_type="application/json"
                )
            return _resp("", status_code=404, url=url)

        with patch(
            "apps.stubs.package_leaks.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = side_effect
            bundle = fetch_evidence("https://x.example/")

        assert "/package.json" not in bundle["responses"]
        assert "/composer.json" in bundle["responses"]


class BodyTruncationTests(unittest.TestCase):
    def test_response_body_truncated_to_max_response_bytes(self) -> None:
        big = '{"name": "' + ("y" * 5000) + '"}'
        responses = {
            "https://x.example/package.json": _resp(
                big, content_type="application/json"
            ),
        }
        config = FetcherConfig(max_response_bytes=1024)
        with patch(
            "apps.stubs.package_leaks.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/", config=config)

        assert len(bundle["responses"]["/package.json"]["body"]) == 1024


class FetcherConfigValidationTests(unittest.TestCase):
    def test_negative_max_response_bytes_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            FetcherConfig(max_response_bytes=-1)
