"""Fetcher tests for stub 1.6 hidden-routes.

The fetcher does:
1. GET / (baseline).
2. GET /.well-known/scanner-nonexistent-<nonce> and GET
   /scanner-nonexistent-<nonce> — soft-404 probes.
3. GET /robots.txt and /sitemap.xml — metadata files.
4. GET each common-path candidate (~8 paths).

The bundle exposes raw responses keyed by path; the runner is
responsible for the soft-404 comparison + dedup. httpx is mocked.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from ..fetcher import COMMON_PATHS, FetcherConfig, fetch_evidence


def _resp(
    body: str = "",
    *,
    status_code: int = 200,
    url: str = "https://x.example/",
) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status_code,
        content=body.encode("utf-8"),
        request=req,
    )


def _matches_path(url: str, path: str) -> bool:
    return url.endswith(path)


def _mock_get(responses: dict[str, httpx.Response]):
    """Map path-suffix → response. Soft-404 probes share a stable
    `__scanner_nonexistent_` substring so the test maps any nonce
    instance to the same response."""
    def side_effect(url, **_kwargs):
        for prefix, resp in responses.items():
            if "scanner_nonexistent" in prefix and "scanner_nonexistent" in url:
                return resp
            if _matches_path(url, prefix):
                return resp
        return _resp("", status_code=404, url=url)
    return side_effect


class CommonPathListTests(unittest.TestCase):
    def test_includes_high_signal_paths(self) -> None:
        # The list MUST cover canonical admin/login/api shapes; the
        # set will grow but never shrink.
        for path in ("/admin", "/login", "/api", "/swagger", "/actuator"):
            assert path in COMMON_PATHS


class BaselineProbeTests(unittest.TestCase):
    def test_captures_baseline(self) -> None:
        responses = {
            "/": _resp("welcome", url="https://x.example/"),
            "scanner_nonexistent": _resp("404 page", status_code=404),
        }
        with patch(
            "apps.stubs.hidden_routes.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        baseline = bundle["baseline"]
        assert baseline["status"] == 200
        assert baseline["body"] == "welcome"


class Soft404Tests(unittest.TestCase):
    def test_records_two_nonce_probes(self) -> None:
        responses = {
            "/": _resp("home"),
            "scanner_nonexistent": _resp("custom 404", status_code=404),
        }
        with patch(
            "apps.stubs.hidden_routes.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        # Two distinct nonce paths in the bundle.
        nonce_paths = [k for k in bundle["probes"] if "scanner_nonexistent" in k]
        assert len(nonce_paths) == 2

    def test_nonce_path_components(self) -> None:
        # One nonce hits /.well-known/, one hits root. Both have a hex
        # suffix; both are recorded.
        responses = {
            "/": _resp("home"),
            "scanner_nonexistent": _resp("", status_code=404),
        }
        with patch(
            "apps.stubs.hidden_routes.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        nonce_paths = [k for k in bundle["probes"] if "scanner_nonexistent" in k]
        has_well_known = any(p.startswith("/.well-known/") for p in nonce_paths)
        has_root = any(
            p.startswith("/scanner_nonexistent_") for p in nonce_paths
        )
        assert has_well_known and has_root


class MetadataFileProbeTests(unittest.TestCase):
    def test_captures_robots_and_sitemap(self) -> None:
        responses = {
            "/": _resp("home"),
            "scanner_nonexistent": _resp("", status_code=404),
            "/robots.txt": _resp("User-agent: *\nDisallow: /admin\n"),
            "/sitemap.xml": _resp("<urlset><loc>/foo</loc></urlset>"),
        }
        with patch(
            "apps.stubs.hidden_routes.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        assert "/robots.txt" in bundle["probes"]
        assert "Disallow: /admin" in bundle["probes"]["/robots.txt"]["body"]
        assert "/sitemap.xml" in bundle["probes"]


class CommonPathProbeTests(unittest.TestCase):
    def test_captures_each_common_path(self) -> None:
        responses = {
            "/": _resp("home"),
            "scanner_nonexistent": _resp("", status_code=404),
            "/admin": _resp("admin login"),
            "/login": _resp("login form"),
        }
        with patch(
            "apps.stubs.hidden_routes.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/")

        assert "/admin" in bundle["probes"]
        assert "/login" in bundle["probes"]


class TransportErrorTests(unittest.TestCase):
    def test_baseline_failure_yields_empty_bundle(self) -> None:
        with patch(
            "apps.stubs.hidden_routes.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = httpx.ConnectError("refused")
            bundle = fetch_evidence("https://x.example/")

        assert bundle == {"baseline": None, "probes": {}}

    def test_per_probe_failure_doesnt_abort_others(self) -> None:
        def side_effect(url, **_kwargs):
            if url == "https://x.example/":
                return _resp("home")
            if "scanner_nonexistent" in url:
                return _resp("", status_code=404)
            if "/admin" in url:
                raise httpx.ConnectError("refused")
            if "/login" in url:
                return _resp("login form")
            return _resp("", status_code=404, url=url)

        with patch(
            "apps.stubs.hidden_routes.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = side_effect
            bundle = fetch_evidence("https://x.example/")

        assert "/admin" not in bundle["probes"]
        assert "/login" in bundle["probes"]


class BodyTruncationTests(unittest.TestCase):
    def test_each_body_truncated_to_max_body_bytes(self) -> None:
        big = "y" * 5000
        responses = {
            "/": _resp(big),
            "scanner_nonexistent": _resp("", status_code=404),
        }
        config = FetcherConfig(max_body_bytes=1024)
        with patch(
            "apps.stubs.hidden_routes.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_get(responses)
            bundle = fetch_evidence("https://x.example/", config=config)

        assert len(bundle["baseline"]["body"]) == 1024


class FetcherConfigValidationTests(unittest.TestCase):
    def test_negative_max_body_bytes_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            FetcherConfig(max_body_bytes=-1)
