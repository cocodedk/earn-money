"""End-to-end runner tests for stub 1.5 with mocked fetcher.

`fetch_evidence` is patched per test so canned probe bundles drive the
runner without real network.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run

from ..runner import run


def _seed() -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(stub_slug="1.5", host="x.example")


def _bundle(responses: dict[str, dict] | None = None) -> dict:
    return {"responses": responses or {}}


def _resp(body: str, content_type: str = "application/json") -> dict:
    return {"status": 200, "content_type": content_type, "body": body}


class PackageJsonDetectionTests(TestCase):
    def test_emits_finding_per_package_in_manifest(self) -> None:
        scan_run, target_run = _seed()
        body = (
            '{"name": "my-app", "version": "1.0.0",'
            ' "dependencies": {"lodash": "4.17.21"}}'
        )
        bundle = _bundle({"/package.json": _resp(body)})
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        # One finding per (package, version) — the app itself + lodash.
        techs = {(f.data["package"], f.data["version"]) for f in Finding.objects.all()}
        assert ("my-app", "1.0.0") in techs
        assert ("lodash", "4.17.21") in techs


class RequirementsTxtDetectionTests(TestCase):
    def test_emits_findings_from_pinned_requirements(self) -> None:
        scan_run, target_run = _seed()
        body = "Django==5.1.0\nrequests==2.31.0"
        bundle = _bundle({"/requirements.txt": _resp(body, "text/plain")})
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        pkgs = {(f.data["package"], f.data["version"]) for f in Finding.objects.all()}
        assert ("Django", "5.1.0") in pkgs
        assert ("requests", "2.31.0") in pkgs


class BannerScanTests(TestCase):
    def test_banner_in_response_body_surfaces_finding(self) -> None:
        # A misconfigured server might return a JS bundle on
        # /package.json (very unusual but defensible). Banner-scan runs
        # alongside parsers so we don't miss disclosures.
        scan_run, target_run = _seed()
        body = "/*! axios 1.6.2 */ var x = 1;"
        bundle = _bundle({
            "/package.json": _resp(body, "application/javascript")
        })
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        pkgs = {(f.data["package"], f.data["version"]) for f in Finding.objects.all()}
        assert ("axios", "1.6.2") in pkgs

    def test_banner_only_path_without_parser_still_scanned(self) -> None:
        # /Gemfile has no MVP parser. If a server somehow returns banner-
        # bearing text from this path, banner-scan must still pick it up.
        scan_run, target_run = _seed()
        body = "/*! my-package 2.0.0 */"
        bundle = _bundle({"/Gemfile": _resp(body, "text/plain")})
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__package="my-package")
        assert finding.data["source_kind"] == "banner"
        assert finding.data["probe_path"] == "/Gemfile"


class FindingShapeTests(TestCase):
    def test_finding_carries_source_kind_and_path(self) -> None:
        scan_run, target_run = _seed()
        body = '{"name": "x", "version": "1.0"}'
        bundle = _bundle({"/package.json": _resp(body)})
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__package="x")
        assert finding.severity == Severity.INFO
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["source_kind"] == "package.json"
        assert finding.data["probe_path"] == "/package.json"
        assert finding.data["source"] == "package_leaks"


class ConfidenceAndSourceTaxonomyTests(TestCase):
    def test_manifest_hit_is_high_confidence_and_path_source(self) -> None:
        scan_run, target_run = _seed()
        body = '{"name": "x", "version": "1.0"}'
        bundle = _bundle({"/package.json": _resp(body)})
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__package="x")
        assert finding.confidence == "high"
        evidence = Evidence.objects.get()
        assert evidence.source == EvidenceSource.PATH

    def test_banner_hit_is_medium_confidence_and_script_source(self) -> None:
        # A banner in a JS body could be a VENDORED copy of the
        # package (not the app's actual declared dep) — medium, not
        # high. And the evidence is JS code, so SCRIPT source.
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/Gemfile": _resp(
                "/*! axios 1.6.2 */", "application/javascript",
            ),
        })
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__package="axios")
        assert finding.confidence == "medium"
        evidence = Evidence.objects.get()
        assert evidence.source == EvidenceSource.SCRIPT


class DeduplicationTests(TestCase):
    def test_same_package_in_multiple_sources_collapsed(self) -> None:
        # If the same (package, version) tuple appears in both
        # package.json AND requirements.txt (rare but real in polyglot
        # repos), surfaces as ONE Finding with TWO Evidence rows —
        # every source channel is preserved for operator triage.
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/package.json": _resp(
                '{"name": "lodash", "version": "4.17.21"}'
            ),
            "/requirements.txt": _resp(
                "lodash==4.17.21", "text/plain"
            ),
        })
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        # One Finding, two Evidence rows linked to it.
        finding = Finding.objects.get(
            data__package="lodash", data__version="4.17.21"
        )
        assert len(finding.data["evidence_ids"]) == 2
        assert Evidence.objects.count() == 2


class NoMatchTests(TestCase):
    def test_empty_bundle_creates_no_findings(self) -> None:
        scan_run, target_run = _seed()
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=_bundle(),
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0

    def test_unparseable_content_creates_no_findings(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/package.json": _resp("not valid json or banner", "text/plain")
        })
        with patch(
            "apps.stubs.package_leaks.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0


class RegistryDispatchTests(TestCase):
    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.5")(run)

    def test_registered_under_1_5(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.5") is run
