"""Transport-error + config-validation tests for stub 1.6 fetcher."""
from __future__ import annotations

import unittest

import httpx
import pytest

from ..fetcher import FetcherConfig, fetch_evidence

from ._fetcher_helpers import _resp, mocked_fetcher


class TransportErrorTests(unittest.TestCase):
    def test_baseline_failure_yields_empty_bundle(self) -> None:
        with mocked_fetcher(get_side_effect=httpx.ConnectError("refused")):
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

        with mocked_fetcher(get_side_effect=side_effect):
            bundle = fetch_evidence("https://x.example/")

        assert "/admin" not in bundle["probes"]
        assert "/login" in bundle["probes"]


class FetcherConfigValidationTests(unittest.TestCase):
    def test_negative_max_body_bytes_raises(self) -> None:
        with pytest.raises(ValueError):
            FetcherConfig(max_body_bytes=-1)
