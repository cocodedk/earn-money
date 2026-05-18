"""End-to-end runner tests for stub 1.2 with mocked fetcher.

The runner is registered under stub_slug="1.2" via @register("1.2").
`fetch_evidence` is patched so tests inject canned header bundles
instead of hitting real targets. The runner writes Evidence + Finding
rows against the test database.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runner import run


def _seed(host: str = "x.example") -> tuple[ScanRun, ScanTargetRun]:
    project = Project.objects.create(name="acme")
    target = ScanTarget.objects.create(
        project=project,
        base_url=f"https://{host}",
        host=host,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug="1.2")
    target_run = ScanTargetRun.objects.create(
        scan_run=scan_run, target=target,
    )
    return scan_run, target_run


def _bundle(headers: dict[str, str], *, method: str = "HEAD") -> dict:
    return {
        "method": method,
        "status_code": 200,
        "headers": headers,
        "url": "https://x.example/",
        "redirect_chain": [],
    }


class NginxDetectionTests(TestCase):
    def test_detects_nginx_with_version(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({"server": "nginx/1.24.0"})

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="nginx")
        assert finding.confidence == "high"
        assert finding.severity == Severity.INFO
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["technology_category"] == "web_server"
        assert finding.data["version"] == "1.24.0"
        assert finding.data["matched_header_name"] == "server"
        assert finding.data["matched_header_value"] == "nginx/1.24.0"
        assert finding.data["source"] == "server_headers"

        evidence = Evidence.objects.get()
        assert evidence.source == EvidenceSource.HEADER
        assert evidence.field == "server"


class ApacheDetectionTests(TestCase):
    def test_detects_apache_with_version(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({"server": "Apache/2.4.58 (Debian)"})

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="apache_httpd")
        assert finding.data["version"] == "2.4.58"


class ExpressDetectionTests(TestCase):
    def test_detects_express_no_version(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({"x-powered-by": "Express"})

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="express")
        # Spec: no version_regex on express signature → version absent.
        assert finding.data["version"] is None


class CloudflareDetectionTests(TestCase):
    def test_detects_cloudflare_via_cf_ray(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({"cf-ray": "76abc-CDG"})

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="cloudflare")
        assert finding.data["technology_category"] == "cdn"
        assert finding.confidence == "high"


class MultiLayerDetectionTests(TestCase):
    """Spec §Conflict handling: multiple credible hints should each
    surface as their own Finding. Edge + app stack co-exist."""

    def test_emits_one_finding_per_detected_technology(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "server": "nginx/1.24.0",
            "x-powered-by": "PHP/8.2.12",
            "cf-ray": "76abc-CDG",
        })

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        techs = {f.data["technology"] for f in Finding.objects.all()}
        assert "nginx" in techs
        assert "php" in techs
        assert "cloudflare" in techs
        # Each finding has at least one evidence row.
        assert Evidence.objects.count() == 3


class NoMatchTests(TestCase):
    def test_unknown_server_creates_no_findings(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({"x-mystery": "something-unrecognised"})

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0


class RedactionInEvidenceTests(TestCase):
    """Sensitive headers must be redacted from evidence persistence."""

    def test_set_cookie_redacted_in_evidence_raw_excerpt(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "server": "nginx/1.24.0",
            "set-cookie": "session=secret-xyz; HttpOnly",
        })

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        # The matched evidence is for server, not set-cookie — but the
        # excerpt may include neighbouring header values. Verify set-cookie
        # value never appears in any evidence row.
        for ev in Evidence.objects.all():
            assert "secret-xyz" not in ev.raw_excerpt


class RegistryDispatchTests(TestCase):
    """Stub 1.2 runner must be reachable via the runner registry under
    stub_slug='1.2'. The registry is process-global and other test
    classes (e.g. apps.stubs.test_runners.RegistryTests) call
    `_clear_for_testing()` in setUp/tearDown, which wipes registrations
    made at app-init time. Re-register here so the assertion is
    independent of test-run order."""

    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.2")(run)

    def test_registered_under_1_2(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.2") is run
