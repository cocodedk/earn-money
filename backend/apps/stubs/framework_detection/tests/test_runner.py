"""End-to-end runner tests with mocked fetcher.

`fetch_evidence` is patched so tests inject canned evidence bundles
instead of hitting real targets. The runner then runs the matcher and
writes Evidence + Finding rows against the test database.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus, Severity
from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runner import run


def _seed(host: str = "dvwa.cocode.dk") -> tuple[ScanRun, ScanTargetRun]:
    project = Project.objects.create(name="acme")
    target = ScanTarget.objects.create(
        project=project,
        base_url=f"https://{host}",
        host=host,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug="1.1")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return scan_run, target_run


class DvwaDetectionTests(TestCase):
    def test_detects_php_via_cookie_and_product_marker(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        bundle = {
            "headers": {"Server": "Apache"},
            "cookies": [{"name": "PHPSESSID", "value": "abc123"}],
            "html_body": "Login :: Damn Vulnerable Web Application (DVWA)",
            "script_names": [],
            "url": "https://dvwa.cocode.dk/",
            "status_code": 200,
        }
        with patch(
            "apps.stubs.framework_detection.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        techs = {f.data["technology"] for f in Finding.objects.all()}
        assert "PHP" in techs
        assert "DVWA" in techs
        # Confidence is high on both → finding.confidence == "high"
        for finding in Finding.objects.all():
            assert finding.confidence == "high"
            assert finding.severity == Severity.INFO
            assert finding.status == FindingStatus.CANDIDATE


class WebGoatDetectionTests(TestCase):
    def test_detects_java_and_webgoat_product_marker(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        bundle = {
            "headers": {"Server": "Apache-Coyote"},
            "cookies": [{"name": "JSESSIONID", "value": "xyz789"}],
            "html_body": "WebGoat - the deliberately insecure web application",
            "script_names": [],
            "url": "https://webgoat.cocode.dk/WebGoat/login",
            "status_code": 200,
        }
        with patch(
            "apps.stubs.framework_detection.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        techs = {f.data["technology"] for f in Finding.objects.all()}
        assert "Java Servlet" in techs
        assert "WebGoat" in techs


class JuiceShopDetectionTests(TestCase):
    def test_detects_angular_spa_and_juice_shop_marker(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        bundle = {
            "headers": {"X-Recruiting": "/#/jobs"},
            "cookies": [],
            "html_body": (
                "<title>OWASP Juice Shop</title>"
                "<app-root></app-root>"
            ),
            "script_names": [
                "runtime.123abc.js",
                "polyfills.456def.js",
                "main.789ghi.js",
            ],
            "url": "https://juiceshop.cocode.dk/",
            "status_code": 200,
        }
        with patch(
            "apps.stubs.framework_detection.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        techs = {f.data["technology"] for f in Finding.objects.all()}
        assert "OWASP Juice Shop" in techs
        assert "Angular SPA" in techs


class NoMatchTests(TestCase):
    def test_blank_target_creates_no_findings(self) -> None:
        scan_run, target_run = _seed("blank.example")
        bundle = {
            "headers": {},
            "cookies": [],
            "html_body": "<html></html>",
            "script_names": [],
            "url": "https://blank.example/",
            "status_code": 200,
        }
        with patch(
            "apps.stubs.framework_detection.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0


class EvidenceShapeTests(TestCase):
    def test_evidence_row_carries_signature_metadata(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        bundle = {
            "headers": {},
            "cookies": [{"name": "PHPSESSID", "value": "abc"}],
            "html_body": "",
            "script_names": [],
            "url": "https://dvwa.cocode.dk/",
            "status_code": 200,
        }
        with patch(
            "apps.stubs.framework_detection.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        evidence = Evidence.objects.get()  # exactly one
        assert evidence.source == "cookie"
        assert evidence.field == "name"
        assert evidence.matched_value == "PHPSESSID"
        assert evidence.data["signature_id"] == "cookie_php_session"
        assert evidence.data["technology"] == "PHP"
        assert evidence.content_hash.startswith("sha256:")


class ExcerptTests(TestCase):
    """Excerpt formatting per evidence source — useful for triage UI."""

    def test_header_excerpt(self) -> None:
        scan_run, target_run = _seed("e.example")
        bundle = {
            "headers": {"X-Powered-By": "Express 4.18.2"},
            "cookies": [], "html_body": "", "script_names": [],
            "url": "https://e.example/", "status_code": 200,
        }
        with patch(
            "apps.stubs.framework_detection.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)
        ev = Evidence.objects.get(data__signature_id="header_express")
        assert "X-Powered-By: Express 4.18.2" in ev.raw_excerpt

    def test_html_body_excerpt_includes_pattern_context(self) -> None:
        scan_run, target_run = _seed("a.example")
        bundle = {
            "headers": {}, "cookies": [],
            "html_body": "x" * 100 + " ng-version=18.2.0 " + "y" * 100,
            "script_names": [],
            "url": "https://a.example/", "status_code": 200,
        }
        with patch(
            "apps.stubs.framework_detection.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)
        ev = Evidence.objects.get(data__signature_id="html_angular_marker")
        assert "ng-version" in ev.raw_excerpt
        assert len(ev.raw_excerpt) <= 200

    def test_script_names_excerpt(self) -> None:
        scan_run, target_run = _seed("a.example")
        bundle = {
            "headers": {}, "cookies": [],
            "html_body": "",
            "script_names": ["runtime.js", "polyfills.js", "main.js"],
            "url": "https://a.example/", "status_code": 200,
        }
        with patch(
            "apps.stubs.framework_detection.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)
        ev = Evidence.objects.get(data__signature_id="angular_bundle_shape")
        assert "scripts:" in ev.raw_excerpt
        assert "runtime.js" in ev.raw_excerpt
