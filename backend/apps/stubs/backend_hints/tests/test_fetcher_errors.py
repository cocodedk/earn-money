"""Transport-error + config-validation tests for stub 1.4 fetcher."""
from __future__ import annotations

import unittest

import httpx
import pytest

from ..fetcher import FetcherConfig, fetch_evidence

from ._fetcher_helpers import _resp, mocked_fetcher


class TransportErrorTests(unittest.TestCase):
    def test_probe_failure_doesnt_abort_other_probes(self) -> None:
        def side_effect(url, **_kwargs):
            if url == "https://x.example/":
                return _resp("home")
            if "/api/" in url:
                raise httpx.ConnectError("api refused")
            if "__scanner_backend_hint_404" in url:
                return _resp("", status_code=404)
            raise AssertionError(f"unmocked: {url}")  # pragma: no cover

        with mocked_fetcher(get_side_effect=side_effect):
            bundle = fetch_evidence("https://x.example/")

        assert "/" in bundle["probes"]
        assert "/api/" not in bundle["probes"]
        assert any(k.startswith("/__scanner_") for k in bundle["probes"])

    def test_all_probes_failing_returns_empty_probes_dict(self) -> None:
        with mocked_fetcher(get_side_effect=httpx.ConnectError("refused")):
            bundle = fetch_evidence("https://x.example/")

        assert bundle["probes"] == {}


class FetcherConfigValidationTests(unittest.TestCase):
    def test_negative_max_body_bytes_raises(self) -> None:
        with pytest.raises(ValueError):
            FetcherConfig(max_body_bytes=-1)
