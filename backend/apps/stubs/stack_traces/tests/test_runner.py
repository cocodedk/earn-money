"""Tests for stub 1.16 runner.run — entry-point + missing-route probes.

End-to-end orchestration: fetch base_url + fetch one random
missing route → matcher → classifier → persist Evidence +
StackTraceFinding rows.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx

from django.test import TestCase

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus
from apps.stubs._test_factories import seed_target_run

from ..runner import run


_BASE = "https://x.example"
_PYTHON_TRACE = (
    "Traceback (most recent call last):\n"
    '  File "/app/views.py", line 42, in get\n'
    "    user = User.objects.get(pk=pk)\n"
    "django.core.exceptions.ObjectDoesNotExist: not found\n"
)


def _resp(body: str, *, status: int = 200, url: str | None = None,
          content_type: str = "text/html") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"content-type": content_type},
        content=body.encode("utf-8"),
        request=httpx.Request("GET", url or f"{_BASE}/"),
    )


@contextmanager
def _mock_fetcher(get_handler):
    with patch(
        "apps.stubs.stack_traces.fetcher.httpx.Client",
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = get_handler
        yield instance


def _seed():
    return seed_target_run(stub_slug="1.16", host="x.example")


class EntryPointHitTests(TestCase):
    def test_entry_point_500_with_traceback_yields_finding(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            url_str = str(url)
            if url_str.endswith("/"):
                return _resp(
                    _PYTHON_TRACE, status=500, url=url_str,
                    content_type="text/html",
                )
            # missing-route probe → plain 404
            return _resp("Not Found", status=404, url=url_str)

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        findings = Finding.objects.filter(scan_run=scan_run)
        assert findings.count() == 1
        finding = findings.first()
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        assert finding.data["signature_family"] == "python_traceback"
        assert finding.data["language_hint"] == "python"
        assert "ObjectDoesNotExist" in finding.data["exception_type"]
        # One evidence row per probe.
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2


class MissingRouteHitTests(TestCase):
    def test_missing_route_500_traceback_yields_finding(self) -> None:
        # Entry point clean, but the random missing-route probe
        # surfaces a debug traceback — the runner reports it.
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            url_str = str(url)
            if url_str.endswith("/"):
                return _resp("<html>OK</html>", status=200, url=url_str)
            return _resp(_PYTHON_TRACE, status=500, url=url_str)

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["signature_family"] == "python_traceback"
        assert finding.data["status_code"] == 500


class NoTraceTests(TestCase):
    def test_both_probes_clean_no_finding(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(
                "<html><h1>Home</h1></html>", status=200,
                url=str(url),
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        # Two evidence rows persist even when nothing matched.
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2
        assert all(
            ev.source == EvidenceSource.HTML
            for ev in Evidence.objects.filter(scan_run=scan_run)
        )


class DocsPageRejectionTests(TestCase):
    def test_docs_page_with_sample_trace_rejected(self) -> None:
        scan_run, target_run = _seed()
        docs_body = (
            "<html><title>Documentation: Python tracebacks</title>"
            f"<pre>{_PYTHON_TRACE}</pre></html>"
        )

        def handler(url, **_kwargs):
            return _resp(docs_body, status=200, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        # Both probes return the docs page; both produce a rejected
        # finding (low confidence).
        findings = Finding.objects.filter(scan_run=scan_run)
        assert findings.count() == 2
        for f in findings:
            assert f.status == FindingStatus.REJECTED
            assert f.confidence == "low"


class TransportFailureTests(TestCase):
    def test_transport_error_recorded_as_evidence_no_finding(self) -> None:
        scan_run, target_run = _seed()

        def handler(*_args, **_kwargs):
            raise httpx.ConnectError("dns")

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        # Two failed probes → two evidence rows status=0, no findings.
        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        evidence = Evidence.objects.filter(scan_run=scan_run)
        assert evidence.count() == 2
        assert all(ev.data["status"] == 0 for ev in evidence)
