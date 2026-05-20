"""Tests for stub 1.17 FU-1 Evidence row shape.

Spec §Persistence + §Safety: `raw_excerpt` is a redacted body
slice (≤ 4096 bytes), `data.selected_headers` is the spec-allowlist
informative fingerprint headers, `data.truncation` flags when the
excerpt is partial.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.stubs._test_factories import seed_target_run

from ..runner import run


_BASE = "https://x.example"


def _resp(body: str, *, status: int = 200, url: str | None = None,
          content_type: str = "application/json",
          extra_headers: dict[str, str] | None = None) -> httpx.Response:
    headers = {"content-type": content_type}
    if extra_headers:
        headers.update(extra_headers)
    return httpx.Response(
        status_code=status,
        headers=headers,
        content=body.encode("utf-8"),
        request=httpx.Request("GET", url or f"{_BASE}/"),
    )


@contextmanager
def _mock_fetcher(get_handler):
    with patch(
        "apps.stubs.verbose_api_errors.fetcher.httpx.Client",
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = get_handler
        yield instance


def _seed():
    return seed_target_run(stub_slug="1.17", host="x.example")


class RedactedExcerptTests(TestCase):
    def test_raw_excerpt_carries_redacted_body_slice(self) -> None:
        scan_run, target_run = _seed()
        body = (
            '{"error": "fail", "token": '
            '"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signaturepart"}'
        )

        def handler(url, **_kwargs):
            return _resp(body, status=200, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        evidence = Evidence.objects.filter(scan_run=scan_run).first()
        assert evidence is not None
        assert "[REDACTED:jwt]" in evidence.raw_excerpt
        assert "eyJhbGciOiJIUzI1NiJ9" not in evidence.raw_excerpt
        assert '"error": "fail"' in evidence.raw_excerpt


class SelectedHeadersTests(TestCase):
    def test_allowlist_populated(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(
                "ok", status=200, url=str(url),
                extra_headers={
                    "Server": "nginx/1.21.6",
                    "X-Powered-By": "Express",
                    "Set-Cookie": "session=secret-must-not-leak",
                    "Authorization": "Bearer leaked-token",
                },
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        ev = Evidence.objects.filter(scan_run=scan_run).first()
        assert ev is not None
        headers = ev.data["selected_headers"]
        assert headers.get("server") == "nginx/1.21.6"
        assert headers.get("x-powered-by") == "Express"
        # Sensitive headers must NEVER be persisted.
        assert "set-cookie" not in headers
        assert "authorization" not in headers
        assert "Set-Cookie" not in headers
        assert "Authorization" not in headers


class FrameworkHintsFindingTests(TestCase):
    """FU-2: when a body carries a framework hint on an error
    response, the finding emits at medium confidence and
    Finding.data.framework_hints is populated."""

    def test_error_with_framework_hint_emits_medium_finding(self) -> None:
        scan_run, target_run = _seed()
        body = (
            "django.core.exceptions.ImproperlyConfigured: "
            "SECRET_KEY setting must not be empty"
        )

        def handler(url, **_kwargs):
            return _resp(
                body, status=500, url=str(url),
                content_type="text/plain",
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        from apps.findings.models import Finding
        finding = Finding.objects.filter(scan_run=scan_run).first()
        assert finding is not None
        assert finding.confidence == "medium"
        assert "django" in finding.data["framework_hints"]


class TruncationTests(TestCase):
    def test_truncation_flag_false_on_short_body(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp("short body", status=200, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        ev = Evidence.objects.filter(scan_run=scan_run).first()
        assert ev is not None
        assert ev.data["truncation"] is False

    def test_truncation_flag_true_when_excerpt_capped(self) -> None:
        scan_run, target_run = _seed()
        big_body = "x" * 5000

        def handler(url, **_kwargs):
            return _resp(big_body, status=200, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        ev = Evidence.objects.filter(scan_run=scan_run).first()
        assert ev is not None
        assert ev.data["truncation"] is True
        assert len(ev.raw_excerpt) <= 4096
