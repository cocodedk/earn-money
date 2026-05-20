"""Tests for stub 1.15 runner.run.

End-to-end orchestration: HTML fetch → bundle-candidate extraction
→ per-bundle fetch → extractors → classifier → persist Evidence +
PublicJavascriptBundle finding rows. fetch_bundle handles both the
HTML and JS fetches — text/html surfaces as kind="non_js" with the
body retained, which the runner exploits to share one HTTP layer
across both probes.
"""
from __future__ import annotations

import httpx

from django.test import TestCase

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus
from apps.stubs._test_factories import seed_target_run

from ..runner import run
from ._helpers import mocked_fetcher, resp


_BASE = "https://x.example"
_HTML_WITH_BUNDLE = (
    '<html><body><script src="/static/app.js"></script></body></html>'
)
_HTML_WITH_CDN = (
    '<html><body>'
    '<script src="https://cdn.example/lib.js"></script>'
    '</body></html>'
)
_JS_WITH_SIGNALS = (
    "// minified bundle\n"
    "var __REACT_DEVTOOLS_GLOBAL_HOOK__ = {};\n"
    "fetch('/api/products');\n"
    "var x = process.env.NEXT_PUBLIC_API_URL;\n"
    "//# sourceMappingURL=app.js.map\n"
)


def _seed():
    return seed_target_run(stub_slug="1.15", host="x.example")


def _html(body: str, *, status: int = 200):
    return resp(
        body, status_code=status, url=f"{_BASE}/",
        headers={"content-type": "text/html"},
    )


class HtmlFetchTests(TestCase):
    def test_html_failure_records_evidence_and_exits(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher(get_side_effect=httpx.ConnectError("dns")):
            run(scan_run, target_run)
        evidence = Evidence.objects.filter(scan_run=scan_run)
        assert evidence.count() == 1
        assert evidence.first().source == EvidenceSource.HTML
        assert evidence.first().data["status"] == 0
        assert Finding.objects.filter(scan_run=scan_run).count() == 0

    def test_html_non_200_records_evidence_and_exits(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({"/": _html("<html/>", status=404)}):
            run(scan_run, target_run)
        ev = Evidence.objects.get(scan_run=scan_run)
        assert ev.data["status"] == 404
        assert Finding.objects.filter(scan_run=scan_run).count() == 0


class SameOriginConfirmedBundleTests(TestCase):
    def test_ok_js_bundle_yields_confirmed_high(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": _html(_HTML_WITH_BUNDLE),
            "/static/app.js": resp(
                _JS_WITH_SIGNALS, status_code=200,
                url=f"{_BASE}/static/app.js",
                headers={"content-type": "application/javascript"},
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        assert finding.stub_slug == "1.15"
        data = finding.data
        assert data["bundle_url"] == f"{_BASE}/static/app.js"
        assert data["same_origin"] is True
        assert data["status_code"] == 200
        assert data["extension"] == "js"
        assert data["source_map_url"] == "app.js.map"
        assert "/api/products" in data["api_path_hints"]
        assert "NEXT_PUBLIC_API_URL" in data["public_env_names"]
        framework_names = {h["name"] for h in data["framework_hints"]}
        assert "react" in framework_names
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2
        assert len(data["evidence_ids"]) == 2

    def test_generic_ct_with_js_url_and_body_yields_medium(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": _html(_HTML_WITH_BUNDLE),
            "/static/app.js": resp(
                "function init(){}", status_code=200,
                url=f"{_BASE}/static/app.js",
                headers={"content-type": "application/octet-stream"},
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.confidence == "medium"
        assert finding.status == FindingStatus.CONFIRMED

    def test_non_js_response_yields_low_rejected(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": _html(_HTML_WITH_BUNDLE),
            "/static/app.js": resp(
                "<html>404</html>", status_code=200,
                url=f"{_BASE}/static/app.js",
                headers={"content-type": "text/html"},
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.REJECTED
        assert finding.confidence == "low"


class CrossOriginCandidateTests(TestCase):
    def test_cdn_script_recorded_as_candidate_without_fetching(self) -> None:
        # include_cdn_metadata=false: spec §Safety bars the runner
        # from GETting an off-origin URL. Direct assertion on the
        # mock guarantees the safety boundary at the HTTP layer.
        scan_run, target_run = _seed()
        with mocked_fetcher({"/": _html(_HTML_WITH_CDN)}) as instance:
            run(scan_run, target_run)
            urls_called = [
                str(call.args[0]) for call in instance.get.call_args_list
            ]
        assert "https://cdn.example/lib.js" not in urls_called
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.confidence == "low"
        assert finding.data["same_origin"] is False
        assert finding.data["skipped_reason"] == (
            "cross_origin_no_include_cdn_metadata"
        )
        # Only the HTML evidence — no bundle fetch happened.
        assert Evidence.objects.filter(scan_run=scan_run).count() == 1


class BundleCountCapTests(TestCase):
    def test_max_bundle_count_capped_at_50(self) -> None:
        scripts = "".join(
            f'<script src="/a{i}.js"></script>' for i in range(60)
        )
        html = f"<html><body>{scripts}</body></html>"
        scan_run, target_run = _seed()
        responses = {"/": _html(html)} | {
            f"/a{i}.js": resp(
                "x", status_code=200, url=f"{_BASE}/a{i}.js",
                headers={"content-type": "application/javascript"},
            )
            for i in range(60)
        }
        with mocked_fetcher(responses):
            run(scan_run, target_run)
        assert Finding.objects.filter(scan_run=scan_run).count() == 50
