"""Capture-path tests for stub 1.4 fetcher — happy path, header
lowercasing, cookie redaction, body truncation, nonce shape."""
from __future__ import annotations

import unittest

from ..fetcher import FetcherConfig, fetch_evidence

from ._fetcher_helpers import _resp, mocked_fetcher


def _three_probes(home: str | None = None, api: str | None = None,
                  not_found: str | None = None) -> dict:
    return {
        "https://x.example/": _resp(home if home is not None else "home"),
        "https://x.example/api/": _resp(api if api is not None else "{}"),
        "https://x.example/__scanner_backend_hint_404": _resp(
            not_found if not_found is not None else "", status_code=404
        ),
    }


class HappyPathTests(unittest.TestCase):
    def test_three_probes_landed_with_paths(self) -> None:
        with mocked_fetcher(_three_probes()):
            bundle = fetch_evidence("https://x.example/")

        probes = bundle["probes"]
        assert "/" in probes
        assert "/api/" in probes
        assert any(k.startswith("/__scanner_") for k in probes)
        assert probes["/"]["body"] == "home"
        assert probes["/api/"]["status"] == 200


class HeaderCaptureTests(unittest.TestCase):
    def test_headers_lowercased_per_probe(self) -> None:
        responses = _three_probes()
        responses["https://x.example/"] = _resp(
            "x", headers={"X-Powered-By": "PHP/8.2.0", "Server": "Apache"},
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        headers = bundle["probes"]["/"]["headers"]
        assert headers["x-powered-by"] == "PHP/8.2.0"
        assert headers["server"] == "Apache"


class CookieCaptureTests(unittest.TestCase):
    def test_cookie_names_extracted_values_dropped(self) -> None:
        # Sensitive value MUST NOT appear anywhere in the bundle.
        responses = _three_probes()
        responses["https://x.example/"] = _resp(
            "x",
            headers={"set-cookie": "JSESSIONID=A1B2C3SECRET; HttpOnly"},
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        cookies = bundle["probes"]["/"]["cookies"]
        assert "JSESSIONID" in cookies
        for probe in bundle["probes"].values():
            assert "A1B2C3SECRET" not in str(probe)

    def test_empty_cookie_name_is_skipped(self) -> None:
        responses = _three_probes()
        responses["https://x.example/"] = _resp(
            "x", headers={"set-cookie": "=orphan-value; Path=/"},
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        assert bundle["probes"]["/"]["cookies"] == []

    def test_attribute_only_cookie_header_is_skipped(self) -> None:
        # A non-RFC-compliant Set-Cookie like `; HttpOnly` (no name=value
        # pair) would otherwise be recorded as a cookie name "; HttpOnly".
        responses = _three_probes()
        responses["https://x.example/"] = _resp(
            "x", headers={"set-cookie": "; HttpOnly"},
        )
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        assert bundle["probes"]["/"]["cookies"] == []


class BodyTruncationTests(unittest.TestCase):
    def test_body_truncated_to_max_body_bytes(self) -> None:
        responses = _three_probes(home="y" * 5000)
        config = FetcherConfig(max_body_bytes=1024)
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/", config=config)

        assert len(bundle["probes"]["/"]["body"]) == 1024


class NonceTests(unittest.TestCase):
    def test_404_path_includes_nonce(self) -> None:
        with mocked_fetcher(_three_probes()):
            bundle = fetch_evidence("https://x.example/")

        nonce_keys = [k for k in bundle["probes"] if "__scanner" in k]
        assert len(nonce_keys) == 1
        path = nonce_keys[0]
        assert path.startswith("/__scanner_backend_hint_404_")
        assert len(path) > len("/__scanner_backend_hint_404_")
