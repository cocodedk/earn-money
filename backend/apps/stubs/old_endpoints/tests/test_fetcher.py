"""Fetcher tests for stub 1.9 old-endpoints."""
from __future__ import annotations

import unittest

import httpx
import pytest

from ..fetcher import FetcherConfig, fetch_evidence

from ._helpers import _resp, mocked_fetcher


def _baseline_responses(home: str = "home") -> dict:
    return {
        "/": _resp(home, url="https://x.example/"),
        "__scanner_control_": _resp("not found", status_code=404),
    }


class BaselineProbeTests(unittest.TestCase):
    def test_captures_baseline(self) -> None:
        with mocked_fetcher(_baseline_responses("welcome")):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["baseline"]["status"] == 200
        assert bundle["baseline"]["body"] == "welcome"


class ControlProbeTests(unittest.TestCase):
    def test_three_namespace_distributed_controls(self) -> None:
        # Spec §3: 3 random control paths across `/`, `/api/`, `/legacy/`
        # so the runner learns the negative shape for each namespace.
        with mocked_fetcher(_baseline_responses()):
            bundle = fetch_evidence("https://x.example/")
        control_paths = [
            k for k in bundle["probes"] if "__scanner_control_" in k
        ]
        assert len(control_paths) == 3

    def test_controls_span_root_api_legacy_prefixes(self) -> None:
        with mocked_fetcher(_baseline_responses()):
            bundle = fetch_evidence("https://x.example/")
        control_paths = [
            k for k in bundle["probes"] if "__scanner_control_" in k
        ]
        prefixes = {p.rsplit("/", 1)[0] + "/" for p in control_paths}
        assert "/" in prefixes
        assert "/api/" in prefixes
        assert "/legacy/" in prefixes


class CandidateProbeTests(unittest.TestCase):
    def test_seeded_paths_probed(self) -> None:
        responses = _baseline_responses()
        responses["/api/v1/users"] = _resp(
            '{"users": []}',
            headers={"Deprecation": "true"},
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence(
                "https://x.example/", extra_paths=("/api/v1/users",),
            )
        assert "/api/v1/users" in bundle["probes"]

    def test_seeded_legacy_paths_dispatched(self) -> None:
        with mocked_fetcher(_baseline_responses()):
            bundle = fetch_evidence("https://x.example/")
        # Spec seeded paths land in the probe dict — verify a sample.
        for path in ("/legacy", "/api/v1", "/v0", "/rest/v1"):
            assert path in bundle["probes"], path


class HeaderCaptureTests(unittest.TestCase):
    def test_response_headers_captured(self) -> None:
        responses = _baseline_responses()
        responses["/api/v1"] = _resp(
            "{}",
            headers={
                "Deprecation": "true",
                "Sunset": "Wed, 31 Dec 2025 23:59:59 GMT",
            },
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        probe = bundle["probes"]["/api/v1"]
        # httpx normalises header keys to lowercase; the signals layer
        # is case-folding-aware so the bundle keeps the wire form.
        assert probe["headers"]["deprecation"] == "true"
        assert "sunset" in probe["headers"]

    def test_cookie_and_auth_headers_dropped(self) -> None:
        # Spec §Safety: "must not persist cookies, authorization
        # headers, tokens". Capture them at fetch time so a debug dump
        # of the bundle can't leak credentials even if Evidence-write
        # redaction is bypassed.
        responses = _baseline_responses()
        responses["/api/v1"] = _resp(
            "{}",
            headers={
                "Set-Cookie": "session=abc",
                "Authorization": "Bearer t",
                "Deprecation": "true",
            },
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        headers = bundle["probes"]["/api/v1"]["headers"]
        assert "set-cookie" not in headers
        assert "authorization" not in headers
        assert "deprecation" in headers

    def test_multi_value_link_header_preserved(self) -> None:
        # RFC 8288 allows multiple Link headers per response. If the
        # fetcher collapsed them via dict(), a rel="deprecation" in
        # any but the last would be lost. Multi-values must combine
        # with comma per RFC 7230 §3.2.2.
        from ..signals import header_deprecation_evidence
        req = httpx.Request("GET", "https://x.example/api/v1")
        multi_resp = httpx.Response(
            status_code=200,
            headers=[
                ("link", '</next>; rel="next"'),
                ("link", '</v2>; rel="deprecation"'),
            ],
            content=b"{}",
            request=req,
        )
        responses = _baseline_responses()
        responses["/api/v1"] = multi_resp
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        link = bundle["probes"]["/api/v1"]["headers"]["link"]
        assert 'rel="deprecation"' in link
        assert "header:Link:rel=deprecation" in header_deprecation_evidence(
            bundle["probes"]["/api/v1"]["headers"],
        )


class RedirectCaptureTests(unittest.TestCase):
    def test_location_header_preserved_on_302(self) -> None:
        # Spec §Request discipline: do not follow redirects. A 302 on
        # /legacy is itself signal — the runner classifies it.
        responses = _baseline_responses()
        responses["/legacy"] = _resp(
            "", status_code=302, headers={"Location": "/"},
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        probe = bundle["probes"]["/legacy"]
        assert probe["status"] == 302
        assert probe["location"] == "/"


class TransportErrorTests(unittest.TestCase):
    def test_baseline_failure_yields_empty_bundle(self) -> None:
        with mocked_fetcher(get_side_effect=httpx.ConnectError("refused")):
            bundle = fetch_evidence("https://x.example/")
        assert bundle == {"baseline": None, "probes": {}}

    def test_per_probe_failure_isolated(self) -> None:
        def side_effect(url, **_kwargs):
            if url == "https://x.example/":
                return _resp("home")
            if "__scanner_control_" in url:
                return _resp("not found", status_code=404)
            if "/legacy/login" in url:
                raise httpx.ConnectError("refused")
            if "/api/v1/users" in url:
                return _resp("{}", headers={"Deprecation": "true"})
            return _resp("", status_code=404, url=url)

        with mocked_fetcher(get_side_effect=side_effect):
            bundle = fetch_evidence(
                "https://x.example/",
                extra_paths=("/legacy/login", "/api/v1/users"),
            )

        assert "/legacy/login" not in bundle["probes"]
        assert "/api/v1/users" in bundle["probes"]


class BodyTruncationTests(unittest.TestCase):
    def test_body_truncated_to_config_cap(self) -> None:
        big = "a" * 100_000
        responses = _baseline_responses()
        responses["/api/v1"] = _resp(big)
        cfg = FetcherConfig(max_body_bytes=1024)
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/", config=cfg)
        assert len(bundle["probes"]["/api/v1"]["body"]) == 1024


class ConfigValidationTests(unittest.TestCase):
    def test_negative_body_cap_rejected(self) -> None:
        with pytest.raises(ValueError):
            FetcherConfig(max_body_bytes=-1)
