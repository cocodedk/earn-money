"""Fetcher tests for stub 1.7 backup-files."""
from __future__ import annotations

import unittest

import httpx
import pytest

from ..fetcher import FetcherConfig, fetch_evidence

from ._helpers import _resp, mocked_fetcher


class SuccessfulProbeTests(unittest.TestCase):
    def test_captures_reachable_archive(self) -> None:
        # /backup.zip is a binary archive in reality, but we stub
        # as a tiny non-HTML body so the SPA filter doesn't trip.
        responses = {
            "https://x.example/backup.zip": _resp(
                "PK\x03\x04...zip bytes...",
                content_type="application/zip",
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        assert "/backup.zip" in bundle["responses"]
        entry = bundle["responses"]["/backup.zip"]
        assert entry["status"] == 200
        assert entry["source_kind"] == "archive"

    def test_dotenv_carries_secret_file_kind(self) -> None:
        responses = {
            "https://x.example/.env": _resp(
                "DATABASE_URL=postgres://x",
                content_type="text/plain",
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        assert bundle["responses"]["/.env"]["source_kind"] == "secret_file"


class HtmlShellFilterTests(unittest.TestCase):
    def test_spa_shell_response_excluded(self) -> None:
        # SPA fallthrough returns the index.html for every unknown path.
        html = "<!DOCTYPE html><html><body><app-root></app-root></body></html>"
        responses = {
            "https://x.example/backup.zip": _resp(
                html, content_type="text/html"
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        assert "/backup.zip" not in bundle["responses"]


class NotFoundTests(unittest.TestCase):
    def test_404_excluded(self) -> None:
        with mocked_fetcher({}):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["responses"] == {}

    def test_500_excluded(self) -> None:
        responses = {
            "https://x.example/backup.zip": _resp(
                "error", status_code=500,
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        assert "/backup.zip" not in bundle["responses"]


class TransportErrorTests(unittest.TestCase):
    def test_per_probe_failure_doesnt_abort_others(self) -> None:
        def side_effect(url, **_kwargs):
            if "/backup.zip" in url:
                raise httpx.ConnectError("refused")
            if "/.env" in url:
                return _resp("DATABASE_URL=x", content_type="text/plain")
            return _resp("", status_code=404, url=url)

        with mocked_fetcher(get_side_effect=side_effect):
            bundle = fetch_evidence("https://x.example/")

        assert "/backup.zip" not in bundle["responses"]
        assert "/.env" in bundle["responses"]


class BodyTruncationTests(unittest.TestCase):
    def test_body_truncated_to_max_response_bytes(self) -> None:
        big = "x" * 5000
        responses = {
            "https://x.example/backup.sql": _resp(
                big, content_type="application/sql",
            ),
        }
        config = FetcherConfig(max_response_bytes=1024)
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/", config=config)

        assert len(bundle["responses"]["/backup.sql"]["body"]) == 1024


class FetcherConfigValidationTests(unittest.TestCase):
    def test_negative_max_response_bytes_raises(self) -> None:
        with pytest.raises(ValueError):
            FetcherConfig(max_response_bytes=-1)
