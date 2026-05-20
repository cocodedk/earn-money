"""Tests for stub 1.19 runner.run — baseline + error-probe orchestration.

End-to-end: fetch base_url + one safe malformed-query probe → matcher
→ classifier → redact → persist Evidence + SqlOrmErrorFinding rows.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus
from apps.stubs._test_factories import seed_target_run

from ..runner import run


_BASE = "https://x.example"
_MYSQL_ERROR = (
    "<h1>500 Internal Server Error</h1>\n"
    "<p>You have an error in your SQL syntax; check the manual near "
    "'FROM users WHERE id=' at line 1</p>"
).encode("utf-8")


def _resp(body: bytes, *, status: int = 200, url: str | None = None,
          content_type: str = "text/html") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"content-type": content_type},
        content=body,
        request=httpx.Request("GET", url or f"{_BASE}/"),
    )


@contextmanager
def _mock_fetcher(get_handler):
    with patch("apps.stubs.sql_orm_errors.fetcher.httpx.Client") as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = get_handler
        yield instance


def _seed():
    return seed_target_run(stub_slug="1.19", host="x.example")


class BaselineHitTests(TestCase):
    def test_baseline_500_with_mysql_error_yields_finding(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(_MYSQL_ERROR, status=500, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        findings = Finding.objects.filter(scan_run=scan_run)
        # Both baseline and probe respond with the MySQL error, so we
        # expect 2 findings (one per probe). Per-target dedup is the
        # cross-run idempotence follow-up.
        assert findings.count() == 2
        finding = findings.first()
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.confidence == "high"
        assert finding.category == "sql_orm_errors.mysql"
        assert finding.data["signature_family"] == "mysql"
        assert finding.data["signature_id"] == "mysql.syntax_error"
        assert "SQL syntax" in finding.data["error_excerpt_redacted"]


class NoMatchTests(TestCase):
    def test_clean_response_yields_zero_findings(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(b"<h1>Welcome</h1>", status=200, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        # Both probes still record Evidence so triage can see what was
        # fetched even on clean responses.
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2


class TransportErrorTests(TestCase):
    def test_transport_error_records_evidence_no_finding(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            raise httpx.TransportError("connection refused")

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        evs = Evidence.objects.filter(scan_run=scan_run)
        assert evs.count() == 2
        assert all(e.data["status"] == 0 for e in evs)


class RedactionTests(TestCase):
    def test_excerpt_redacts_email_in_error_text(self) -> None:
        scan_run, target_run = _seed()
        # MySQL error mentioning an email — must be redacted.
        body = (
            b"You have an error in your SQL syntax near 'WHERE email="
            b"\"victim@example.org\" AND' at line 1"
        )

        def handler(url, **_kwargs):
            return _resp(body, status=500, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        finding = Finding.objects.filter(scan_run=scan_run).first()
        assert finding is not None
        assert "victim@example.org" not in finding.data["error_excerpt_redacted"]
        assert "[REDACTED:email]" in finding.data["error_excerpt_redacted"]
