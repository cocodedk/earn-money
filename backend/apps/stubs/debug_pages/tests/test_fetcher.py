"""Tests for stub 1.10 fetch_evidence — multi-probe HTTP fetcher with
max_response_bytes truncation and header allowlist."""
from __future__ import annotations

import unittest

import httpx

from ..fetcher import CONTROL_MARKER, FetcherConfig, fetch_evidence
from ._helpers import mocked_fetcher, resp


class FetcherBundleShapeTests(unittest.TestCase):
    def test_baseline_and_probes_keyed_by_path(self) -> None:
        with mocked_fetcher({
            "/": resp("homepage", status_code=200),
            "/phpinfo.php": resp("phpinfo()", status_code=200),
        }):
            bundle = fetch_evidence("https://x.example")

        assert bundle["baseline"] is not None
        assert bundle["baseline"]["status"] == 200
        assert bundle["baseline"]["body"] == "homepage"
        assert "/phpinfo.php" in bundle["probes"]
        assert bundle["probes"]["/phpinfo.php"]["body"] == "phpinfo()"

    def test_baseline_unreachable_returns_empty_probes(self) -> None:
        def raise_(_url, **_kwargs):
            raise httpx.ConnectError("baseline unreachable")

        with mocked_fetcher(get_side_effect=raise_):
            bundle = fetch_evidence("https://x.example")
        assert bundle["baseline"] is None
        assert bundle["probes"] == {}


class TruncationTests(unittest.TestCase):
    def test_body_truncated_to_max_bytes(self) -> None:
        long_body = "x" * 10000
        with mocked_fetcher({
            "/": resp("home", status_code=200),
            "/phpinfo.php": resp(long_body, status_code=200),
        }):
            bundle = fetch_evidence(
                "https://x.example", config=FetcherConfig(max_body_bytes=256),
            )
        assert len(bundle["probes"]["/phpinfo.php"]["body"]) == 256


class HeaderAllowlistTests(unittest.TestCase):
    def test_only_allowlisted_headers_captured(self) -> None:
        with mocked_fetcher({
            "/": resp("home", status_code=200),
            "/_profiler/": resp(
                "profiler body",
                status_code=200,
                headers={
                    "X-Debug-Token": "abc123",
                    "Set-Cookie": "session=secret-token",
                    "Authorization": "Bearer pretend-token",
                    "X-Powered-By": "PHP/8.2",
                    "Content-Type": "text/html",
                },
            ),
        }):
            bundle = fetch_evidence("https://x.example")

        captured = bundle["probes"]["/_profiler/"]["headers"]
        assert "x-debug-token" in captured
        assert "x-powered-by" in captured
        assert "content-type" in captured
        # Spec §Safety: cookies, authorization must NEVER reach the bundle.
        assert "set-cookie" not in captured
        assert "authorization" not in captured
        # And no captured value should be the secret-cookie string.
        assert "secret-token" not in str(captured)


class PerProbeTransportErrorIsolationTests(unittest.TestCase):
    def test_one_failing_probe_doesnt_stop_the_scan(self) -> None:
        def side_effect(url, **_kwargs):
            if url.endswith("/phpinfo.php"):
                raise httpx.ConnectError("DNS timeout")
            if url.endswith("/"):
                return resp("home", status_code=200)
            if url.endswith("/actuator"):
                return resp(
                    '{"_links":{"self":{}, "health":{}}}',
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                )
            return resp("", status_code=404, url=url)

        with mocked_fetcher(get_side_effect=side_effect):
            bundle = fetch_evidence("https://x.example")

        # /phpinfo.php raised → it's absent from probes
        assert "/phpinfo.php" not in bundle["probes"]
        # /actuator probe still landed
        assert "/actuator" in bundle["probes"]


class ConfigValidationTests(unittest.TestCase):
    def test_negative_max_body_bytes_rejected(self) -> None:
        with unittest.TestCase.assertRaises(self, ValueError):
            FetcherConfig(max_body_bytes=-1)


class ControlMarkerTests(unittest.TestCase):
    def test_marker_constant_exported(self) -> None:
        # Runner skips paths containing CONTROL_MARKER; the symbol
        # must be a non-empty string so the membership check is
        # well-defined.
        assert isinstance(CONTROL_MARKER, str)
        assert CONTROL_MARKER
