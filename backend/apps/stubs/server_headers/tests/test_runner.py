"""End-to-end runner tests for stub 1.2 with mocked fetcher.

`fetch_evidence` is patched in every test so canned header bundles
drive the runner without real network.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run

from ..redaction import redact_headers
from ..runner import run


def _seed() -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(stub_slug="1.2", host="x.example")


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
        assert len(finding.data["evidence_ids"]) == len(
            finding.data["signature_ids"]
        )

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

    def test_two_cloudflare_signatures_share_one_finding(self) -> None:
        """cf-ray AND cf-cache-status both indicate cloudflare. Spec
        §Conflict handling says collapse same-technology hits into one
        Finding — but the Finding must reference BOTH signatures and
        BOTH Evidence rows."""
        scan_run, target_run = _seed()
        bundle = _bundle(
            {"cf-ray": "76abc-CDG", "cf-cache-status": "HIT"}
        )

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="cloudflare")
        assert len(finding.data["signature_ids"]) == 2
        assert len(finding.data["evidence_ids"]) == 2
        assert Evidence.objects.filter(field="cf-ray").exists()
        assert Evidence.objects.filter(field="cf-cache-status").exists()


class MultiLayerDetectionTests(TestCase):
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
        assert Finding.objects.count() == 3
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


class RedactionInRunnerTests(TestCase):
    """Spec §Persistence: secret-bearing headers must be redacted before
    persistence. Verify the runner actually calls redact_headers (spy
    on the call) AND that the post-redaction headers are what feeds the
    matcher and the Evidence raw_excerpt."""

    def test_runner_calls_redact_headers_before_matching(self) -> None:
        """The spy assertion is the strict gate: the runner MUST call
        `redact_headers(bundle["headers"])` before anything else looks
        at the headers. If a future refactor sneaks raw bundle headers
        to the matcher, this test fails."""
        scan_run, target_run = _seed()
        bundle = _bundle({
            "server": "nginx/1.24.0",
            "set-cookie": "session=secret-xyz; HttpOnly",
        })

        with patch(
            "apps.stubs.server_headers.runner.fetch_evidence",
            return_value=bundle,
        ), patch(
            "apps.stubs.server_headers.runner.redact_headers",
            wraps=redact_headers,
        ) as redact_spy:
            run(scan_run, target_run)

        redact_spy.assert_called_once_with(bundle["headers"])


class RegistryDispatchTests(TestCase):
    """Stub 1.2 runner must be reachable via the runner registry under
    stub_slug='1.2'. The registry is process-global and other test
    classes (apps.stubs.test_runners.RegistryTests) call
    _clear_for_testing() in setUp/tearDown, which wipes registrations
    made at app-init time. Re-register here so the assertion is
    independent of test-run order."""

    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.2")(run)

    def test_registered_under_1_2(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.2") is run
