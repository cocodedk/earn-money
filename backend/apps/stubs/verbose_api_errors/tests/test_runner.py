"""Tests for stub 1.17 runner.run — baseline + nonexistent-API-sibling."""
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
_JSON_ERROR = (
    '{"error": "fail", "stack": "Traceback...",'
    ' "file": "/app/main.py", "line": 42}'
)


def _resp(body: str, *, status: int = 200, url: str | None = None,
          content_type: str = "application/json") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"content-type": content_type},
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


class StrongIndicatorTests(TestCase):
    def test_baseline_500_with_json_stack_yields_high_confirmed(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            url_str = str(url)
            if url_str.endswith("/"):
                return _resp(_JSON_ERROR, status=500, url=url_str)
            return _resp('{"error":"not found"}', status=404, url=url_str)

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        data = finding.data
        assert "json_debug_field" in data["disclosure_types"]
        assert "source_path" in data["disclosure_types"]
        assert data["probe_kind"] == "baseline"
        assert any("/app/main.py" in p for p in data["file_path_hints"])
        # Two evidence rows recorded (baseline + nonexistent).
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2

    def test_nonexistent_probe_triggers_framework_500(self) -> None:
        # Baseline clean; the random nonexistent_api_sibling probe
        # surfaces a stack-bearing JSON 500 → finding from the probe.
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            url_str = str(url)
            if "__scanner_nonexistent_" in url_str:
                return _resp(_JSON_ERROR, status=500, url=url_str)
            return _resp('{"ok":true}', status=200, url=url_str)

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["probe_kind"] == "nonexistent_api_sibling"
        assert finding.confidence == "high"


class CleanResponsesTests(TestCase):
    def test_both_probes_clean_no_finding(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(
                '{"message": "ok"}', status=200, url=str(url),
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        # Evidence still recorded per probe.
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2

    def test_generic_404_no_finding(self) -> None:
        # Spec negative assertion — a normal not-found page with no
        # debug data must not create a finding.
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(
                '{"error":"not found"}', status=404, url=str(url),
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0


class TransportFailureTests(TestCase):
    def test_transport_error_recorded_as_evidence(self) -> None:
        scan_run, target_run = _seed()

        def handler(*_args, **_kwargs):
            raise httpx.ConnectError("dns")

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        evidence = Evidence.objects.filter(scan_run=scan_run)
        assert evidence.count() == 2
        assert all(ev.data["status"] == 0 for ev in evidence)
        # Transport-error rows have no body — excerpt empty, no
        # truncation, no headers.
        for ev in evidence:
            assert ev.raw_excerpt == ""
            assert ev.data["selected_headers"] == {}
            assert ev.data["truncation"] is False


# FU-1 Evidence-shape tests live in test_runner_evidence.py.
