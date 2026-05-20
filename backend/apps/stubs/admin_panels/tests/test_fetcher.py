"""Fetcher tests for stub 1.8 admin-panels."""
from __future__ import annotations

import unittest

import httpx
import pytest

from ..fetcher import FetcherConfig, fetch_evidence

from ._helpers import _resp, mocked_fetcher


def _baseline_responses(home: str = "home") -> dict:
    return {
        "/": _resp(home, url="https://x.example/"),
        "scanner-baseline-": _resp("not found", status_code=404),
    }


class BaselineProbeTests(unittest.TestCase):
    def test_captures_baseline(self) -> None:
        with mocked_fetcher(_baseline_responses("welcome")):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["baseline"]["status"] == 200
        assert bundle["baseline"]["body"] == "welcome"


class NonceProbeTests(unittest.TestCase):
    def test_two_nonce_probes_recorded(self) -> None:
        with mocked_fetcher(_baseline_responses()):
            bundle = fetch_evidence("https://x.example/")
        nonce_paths = [k for k in bundle["probes"] if "scanner-baseline-" in k]
        assert len(nonce_paths) == 2


class CandidateProbeTests(unittest.TestCase):
    def test_captures_admin_path(self) -> None:
        responses = _baseline_responses()
        responses["/admin"] = _resp(
            '<form><input type="password" name="pw"></form>',
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        assert "/admin" in bundle["probes"]
        assert bundle["probes"]["/admin"]["status"] == 200


class RedirectCaptureTests(unittest.TestCase):
    def test_location_header_preserved_on_302(self) -> None:
        # Spec: follow_redirects=False — we want the raw 302 so the
        # Location header is itself signal (e.g., /admin → /admin/login).
        responses = _baseline_responses()
        responses["/admin"] = _resp(
            "", status_code=302,
            headers={"Location": "/admin/login"},
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        probe = bundle["probes"]["/admin"]
        assert probe["status"] == 302
        assert probe["location"] == "/admin/login"


class TransportErrorTests(unittest.TestCase):
    def test_baseline_failure_yields_empty_bundle(self) -> None:
        with mocked_fetcher(get_side_effect=httpx.ConnectError("refused")):
            bundle = fetch_evidence("https://x.example/")
        assert bundle == {"baseline": None, "probes": {}}

    def test_per_probe_failure_isolated(self) -> None:
        def side_effect(url, **_kwargs):
            if url == "https://x.example/":
                return _resp("home")
            if "scanner-baseline-" in url:
                return _resp("not found", status_code=404)
            if "/admin" in url and "/admin/" not in url:
                raise httpx.ConnectError("refused")
            if "/dashboard" in url:
                return _resp("ok")
            return _resp("", status_code=404, url=url)

        with mocked_fetcher(get_side_effect=side_effect):
            bundle = fetch_evidence("https://x.example/")

        assert "/admin" not in bundle["probes"]
        assert "/dashboard" in bundle["probes"]


class BodyTruncationTests(unittest.TestCase):
    def test_body_truncated_to_max_body_bytes(self) -> None:
        responses = _baseline_responses("y" * 5000)
        config = FetcherConfig(max_body_bytes=1024)
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/", config=config)
        assert len(bundle["baseline"]["body"]) == 1024


class FetcherConfigValidationTests(unittest.TestCase):
    def test_negative_max_body_bytes_raises(self) -> None:
        with pytest.raises(ValueError):
            FetcherConfig(max_body_bytes=-1)
