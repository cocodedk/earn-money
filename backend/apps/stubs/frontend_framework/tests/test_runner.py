"""End-to-end runner tests for stub 1.3 with mocked fetcher.

`fetch_evidence` is patched in every test so canned evidence bundles
drive the runner without real network.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus, Severity

from ..runner import run

from ._runner_helpers import make_bundle as _bundle
from ._runner_helpers import seed_for_1_3 as _seed


class AngularDetectionTests(TestCase):
    def test_detects_angular_with_version(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle(
            html_body='<html><body><app-root ng-version="16.2.0"></app-root></body></html>',
        )
        with patch(
            "apps.stubs.frontend_framework.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="Angular")
        assert finding.confidence == "high"
        assert finding.severity == Severity.INFO
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["technology_category"] == "framework"
        assert finding.data["version"] == "16.2.0"
        assert finding.data["source"] == "frontend_framework"
        assert len(finding.data["evidence_ids"]) == len(
            finding.data["signature_ids"]
        )


class NextJsDetectionTests(TestCase):
    def test_detects_next_via_data_marker(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle(
            html_body='<script id="__NEXT_DATA__" type="application/json">{}</script>',
            script_paths=["/_next/static/chunks/app.js"],
        )
        with patch(
            "apps.stubs.frontend_framework.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="Next.js")
        # Two signatures: __NEXT_DATA__ in body, /_next/static/ in scripts.
        assert len(finding.data["signature_ids"]) == 2
        assert "next_data" in finding.data["signature_ids"]
        assert "next_static_path" in finding.data["signature_ids"]


class JqueryDetectionTests(TestCase):
    def test_detects_jquery_with_version(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle(
            script_paths=["/static/jquery-3.7.1.min.js"],
        )
        with patch(
            "apps.stubs.frontend_framework.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="jQuery")
        assert finding.data["version"] == "3.7.1"
        assert finding.data["technology_category"] == "library"


class ReactDetectionTests(TestCase):
    def test_detects_react_via_asset_body(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle(
            script_paths=["/static/vendor.js"],
            asset_bodies={"vendor.js": "function react-dom(){}"},
        )
        with patch(
            "apps.stubs.frontend_framework.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="React")
        # react_dom_in_asset is the matched signature; confidence is medium.
        assert finding.confidence == "medium"


class MultiTechDetectionTests(TestCase):
    """A real Next.js+React+jQuery+Bootstrap site: each tech surfaces
    its own Finding with the appropriate signatures attached."""

    def test_emits_one_finding_per_technology(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle(
            html_body='<div id="__NEXT_DATA__"></div>',
            script_paths=[
                "/_next/static/chunks/app.js",
                "/static/jquery-3.7.1.min.js",
                "/static/bootstrap.min.css",
            ],
            asset_bodies={"vendor.js": "react-dom is here"},
        )
        with patch(
            "apps.stubs.frontend_framework.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        techs = {f.data["technology"] for f in Finding.objects.all()}
        assert "Next.js" in techs
        assert "jQuery" in techs
        assert "Bootstrap" in techs
        assert "React" in techs


class ContainsAllDetectionTests(TestCase):
    """contains_all signatures (Angular bundle paths, ngcontent markers)
    carry a list-valued value_pattern — runner's matched_value summary
    has to handle that shape."""

    def test_detects_angular_via_bundle_paths(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle(
            script_paths=[
                "/static/runtime.abc.js",
                "/static/polyfills.def.js",
                "/static/main.ghi.js",
            ],
        )
        with patch(
            "apps.stubs.frontend_framework.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="Angular")
        evidence = Evidence.objects.get(
            data__signature_id="angular_bundle_paths"
        )
        # contains_all stores the joined pattern list as matched_value.
        assert "runtime" in evidence.matched_value
        assert "polyfills" in evidence.matched_value
        assert "main" in evidence.matched_value


class NoMatchTests(TestCase):
    def test_empty_bundle_creates_no_findings(self) -> None:
        scan_run, target_run = _seed()
        with patch(
            "apps.stubs.frontend_framework.runner.fetch_evidence",
            return_value=_bundle(),
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0

    def test_static_html_with_no_frontend_markers_creates_no_findings(
        self,
    ) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle(html_body="<html><body><h1>plain</h1></body></html>")
        with patch(
            "apps.stubs.frontend_framework.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0


class RegistryDispatchTests(TestCase):
    """Stub 1.3 runner must be reachable via the runner registry under
    stub_slug='1.3'. Re-register defensively in setUp because
    apps.stubs.test_runners.RegistryTests calls _clear_for_testing()."""

    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.3")(run)

    def test_registered_under_1_3(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.3") is run
