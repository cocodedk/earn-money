"""Capture-path tests for stub 1.6 fetcher — baseline, nonces, metadata
files, common paths, body truncation."""
from __future__ import annotations

import unittest

from ..fetcher import COMMON_PATHS, FetcherConfig, fetch_evidence

from ._fetcher_helpers import _resp, mocked_fetcher


def _nonces_only() -> dict:
    return {
        "/": _resp("home"),
        "scanner_nonexistent": _resp("", status_code=404),
    }


class CommonPathListTests(unittest.TestCase):
    def test_includes_high_signal_paths(self) -> None:
        for path in ("/admin", "/login", "/api", "/swagger", "/actuator"):
            assert path in COMMON_PATHS


class BaselineProbeTests(unittest.TestCase):
    def test_captures_baseline(self) -> None:
        responses = {
            "/": _resp("welcome", url="https://x.example/"),
            "scanner_nonexistent": _resp("404 page", status_code=404),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        baseline = bundle["baseline"]
        assert baseline["status"] == 200
        assert baseline["body"] == "welcome"


class Soft404Tests(unittest.TestCase):
    def test_records_two_nonce_probes(self) -> None:
        with mocked_fetcher(_nonces_only()):
            bundle = fetch_evidence("https://x.example/")
        nonce_paths = [k for k in bundle["probes"] if "scanner_nonexistent" in k]
        assert len(nonce_paths) == 2

    def test_nonce_path_components(self) -> None:
        with mocked_fetcher(_nonces_only()):
            bundle = fetch_evidence("https://x.example/")
        nonce_paths = [k for k in bundle["probes"] if "scanner_nonexistent" in k]
        has_well_known = any(p.startswith("/.well-known/") for p in nonce_paths)
        has_root = any(
            p.startswith("/scanner_nonexistent_") for p in nonce_paths
        )
        assert has_well_known and has_root


class MetadataFileProbeTests(unittest.TestCase):
    def test_captures_robots_and_sitemap(self) -> None:
        responses = _nonces_only()
        responses["/robots.txt"] = _resp("User-agent: *\nDisallow: /admin\n")
        responses["/sitemap.xml"] = _resp("<urlset><loc>/foo</loc></urlset>")
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        assert "/robots.txt" in bundle["probes"]
        assert "Disallow: /admin" in bundle["probes"]["/robots.txt"]["body"]
        assert "/sitemap.xml" in bundle["probes"]


class CommonPathProbeTests(unittest.TestCase):
    def test_captures_each_common_path(self) -> None:
        responses = _nonces_only()
        responses["/admin"] = _resp("admin login")
        responses["/login"] = _resp("login form")
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        assert "/admin" in bundle["probes"]
        assert "/login" in bundle["probes"]


class BodyTruncationTests(unittest.TestCase):
    def test_each_body_truncated_to_max_body_bytes(self) -> None:
        responses = _nonces_only()
        responses["/"] = _resp("y" * 5000)
        config = FetcherConfig(max_body_bytes=1024)
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/", config=config)

        assert len(bundle["baseline"]["body"]) == 1024
