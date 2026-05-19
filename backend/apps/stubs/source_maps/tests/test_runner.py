"""Tests for stub 1.14 runner.run.

End-to-end orchestration: HTML fetch → asset extraction → per-asset
fetch + sourceMappingURL extraction → resolve → map fetch (or
``.map`` fallback) → classify → persist Evidence + SourceMapFinding.
"""
from __future__ import annotations

import json

from django.test import TestCase

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.stubs._test_factories import seed_target_run

from ..runner import run
from ._helpers import mocked_fetcher, resp


_BASE = "https://x.example"
_HTML_WITH_ASSET = (
    '<html><body>'
    '<script src="/static/app.js"></script>'
    '</body></html>'
)
_VALID_MAP = json.dumps({
    "version": 3,
    "sources": ["webpack://app/src/main.ts"],
    "sourcesContent": ["console.log('main');"],
    "mappings": "AAAA",
})
_JS_WITH_COMMENT = (
    "console.log('app');\n//# sourceMappingURL=app.js.map\n"
)
_JS_WITHOUT_COMMENT = "console.log('plain');\n"


def _seed() -> tuple:
    return seed_target_run(stub_slug="1.14", host="x.example")


class ConfirmedFindingTests(TestCase):
    def test_comment_referenced_map_yields_confirmed_high(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp(_HTML_WITH_ASSET, status_code=200, url=f"{_BASE}/"),
            "/static/app.js": resp(
                _JS_WITH_COMMENT, status_code=200,
                url=f"{_BASE}/static/app.js",
            ),
            "/static/app.js.map": resp(
                _VALID_MAP, status_code=200,
                url=f"{_BASE}/static/app.js.map",
            ),
        }):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        assert finding.severity == Severity.LOW  # sourcesContent present
        assert finding.data["map_reference_type"] == "comment"
        assert "valid_source_map" in finding.data["indicators"]
        assert finding.data["sources_count"] == 1

    def test_fallback_map_yields_confirmed_medium(self) -> None:
        # No sourceMappingURL comment in the asset, but /static/app.js.map
        # exists → fallback probe finds it.
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp(_HTML_WITH_ASSET, status_code=200, url=f"{_BASE}/"),
            "/static/app.js": resp(
                _JS_WITHOUT_COMMENT, status_code=200,
                url=f"{_BASE}/static/app.js",
            ),
            "/static/app.js.map": resp(
                _VALID_MAP, status_code=200,
                url=f"{_BASE}/static/app.js.map",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "medium"
        assert finding.data["map_reference_type"] == "fallback"


class RejectedFindingTests(TestCase):
    def test_404_map_yields_rejected(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp(_HTML_WITH_ASSET, status_code=200, url=f"{_BASE}/"),
            "/static/app.js": resp(
                _JS_WITHOUT_COMMENT, status_code=200,
                url=f"{_BASE}/static/app.js",
            ),
            "/static/app.js.map": resp("", status_code=404),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.REJECTED
        assert finding.data["map_reference_type"] == "fallback"


class CandidateFindingTests(TestCase):
    def test_inline_data_url_yields_candidate(self) -> None:
        scan_run, target_run = _seed()
        body_with_inline = (
            "x();\n//# sourceMappingURL=data:application/json;base64,e30=\n"
        )
        with mocked_fetcher({
            "/": resp(_HTML_WITH_ASSET, status_code=200, url=f"{_BASE}/"),
            "/static/app.js": resp(
                body_with_inline, status_code=200,
                url=f"{_BASE}/static/app.js",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["map_reference_type"] == "inline_data_url"


class NoAssetsTests(TestCase):
    def test_no_assets_in_html_writes_html_evidence_only(self) -> None:
        # HTML has no script/link tags → no asset evidence, no
        # findings. The runner records the HTML probe outcome as
        # diagnostic evidence so the audit row still exists.
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp("<html></html>", status_code=200, url=f"{_BASE}/"),
        }):
            run(scan_run, target_run)
        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        assert Evidence.objects.filter(
            scan_run=scan_run, source=EvidenceSource.HTML,
        ).count() == 1

    def test_html_fetch_failure_writes_diagnostic_evidence(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({"/": resp("", status_code=500, url=f"{_BASE}/")}):
            run(scan_run, target_run)
        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        assert Evidence.objects.filter(scan_run=scan_run).count() == 1

    def test_asset_fetch_failure_skips_finding(self) -> None:
        # HTML OK, but the linked asset returns 500 → no finding,
        # only asset evidence (status recorded for audit). The runner
        # never reaches the comment-extraction or fallback paths.
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp(_HTML_WITH_ASSET, status_code=200, url=f"{_BASE}/"),
            "/static/app.js": resp("", status_code=500),
        }):
            run(scan_run, target_run)
        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        # HTML evidence + asset evidence
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2


class EvidenceTrailTests(TestCase):
    def test_confirmed_finding_persists_three_evidence_rows(self) -> None:
        # Spec §Persistence: one Evidence per important HTTP
        # response. For a comment-confirmed path that's HTML +
        # asset + map.
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp(_HTML_WITH_ASSET, status_code=200, url=f"{_BASE}/"),
            "/static/app.js": resp(
                _JS_WITH_COMMENT, status_code=200,
                url=f"{_BASE}/static/app.js",
            ),
            "/static/app.js.map": resp(
                _VALID_MAP, status_code=200,
                url=f"{_BASE}/static/app.js.map",
            ),
        }):
            run(scan_run, target_run)
        evidence = Evidence.objects.filter(scan_run=scan_run)
        sources = sorted(e.source for e in evidence)
        assert sources == [EvidenceSource.HTML, EvidenceSource.PATH,
                           EvidenceSource.SCRIPT]

    def test_evidence_ids_referenced_on_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp(_HTML_WITH_ASSET, status_code=200, url=f"{_BASE}/"),
            "/static/app.js": resp(
                _JS_WITH_COMMENT, status_code=200,
                url=f"{_BASE}/static/app.js",
            ),
            "/static/app.js.map": resp(
                _VALID_MAP, status_code=200,
                url=f"{_BASE}/static/app.js.map",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        # asset + map evidence IDs referenced; HTML page is diagnostic
        assert len(finding.data["evidence_ids"]) == 2
