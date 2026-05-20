"""Stub 1.17 FU-3 — weak-signal negative-assertion regression tests.

Spec §"Negative assertions": these responses must NOT create a
finding even though they superficially look like errors.

Split out of test_negative_assertions.py to keep both files under
the 200-line cap.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding
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
        status_code=status, headers=headers,
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


class WeakSignalTests(TestCase):
    def test_rfc_7807_problem_details_no_finding(self) -> None:
        # Spec line 390: RFC 7807 without stack/trace/exception/path/
        # SQL/framework → no finding.
        scan_run, target_run = _seed()
        body = (
            '{"type": "https://example.com/probs/oops", '
            '"title": "Bad Request", "status": 400, '
            '"detail": "field is required"}'
        )

        def handler(url, **_kwargs):
            return _resp(
                body, status=400, url=str(url),
                content_type="application/problem+json",
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        # Evidence is still recorded (operator triage benefits).
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2

    def test_server_header_alone_no_finding(self) -> None:
        # Spec line 393: Server header alone must not create a finding.
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(
                "ok", status=200, url=str(url),
                content_type="text/plain",
                extra_headers={"Server": "nginx/1.21.6"},
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0

    def test_validation_error_without_internals_no_finding(self) -> None:
        # Spec line 391: normal validation errors without internals
        # must not create a finding.
        scan_run, target_run = _seed()
        body = (
            '{"errors": [{"field": "email", "message": '
            '"is required"}]}'
        )

        def handler(url, **_kwargs):
            return _resp(body, status=422, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
