"""End-to-end runner tests for stub 1.4 with mocked fetcher.

`fetch_evidence` is patched per test so canned bundles drive the
runner without real network.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run

from ..runner import run


def _seed() -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(stub_slug="1.4", host="x.example")


def _bundle(probes: dict[str, dict] | None = None) -> dict:
    return {"probes": probes or {}}


def _probe(
    headers: dict[str, str] | None = None,
    cookies: list[str] | None = None,
    body: str = "",
    status: int = 200,
) -> dict:
    return {
        "headers": headers or {},
        "cookies": cookies or [],
        "body": body,
        "status": status,
    }


class ExpressDetectionTests(TestCase):
    def test_detects_express_via_powered_by_header(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/": _probe(headers={"x-powered-by": "Express"}),
        })
        with patch(
            "apps.stubs.backend_hints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="Express")
        assert finding.confidence == "high"
        assert finding.severity == Severity.INFO
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["source"] == "backend_hints"
        assert finding.data["technology_category"] == "app_framework"


class PhpDetectionTests(TestCase):
    def test_detects_php_with_version(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/": _probe(headers={"x-powered-by": "PHP/8.2.12"}),
        })
        with patch(
            "apps.stubs.backend_hints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="PHP")
        assert finding.data["version"] == "8.2.12"


class JavaDetectionTests(TestCase):
    def test_detects_java_via_jsessionid_cookie(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/": _probe(cookies=["JSESSIONID"]),
        })
        with patch(
            "apps.stubs.backend_hints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="Java Servlet")
        assert finding.data["technology_category"] == "app_runtime"


class DjangoDetectionTests(TestCase):
    def test_detects_django_via_csrftoken_cookie(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/": _probe(cookies=["csrftoken", "sessionid"]),
        })
        with patch(
            "apps.stubs.backend_hints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        # Both csrftoken (high) and sessionid (medium) are Django
        # signatures — collapsed to one Django finding.
        django = Finding.objects.get(data__technology="Django")
        assert len(django.data["signature_ids"]) == 2
        assert "cookie_csrftoken_django" in django.data["signature_ids"]


class SpringDetectionTests(TestCase):
    def test_detects_spring_via_whitelabel_body(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/": _probe(body="ok"),
            "/__scanner_backend_hint_404_abc": _probe(
                body="<h1>Whitelabel Error Page</h1>", status=404
            ),
        })
        with patch(
            "apps.stubs.backend_hints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        spring = Finding.objects.get(data__technology="Spring Boot")
        assert spring.data["technology_category"] == "error_page"


class MultiBackendTests(TestCase):
    """A target running Express in front of PHP — both technologies
    surface separate Findings."""

    def test_emits_one_finding_per_backend(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/": _probe(
                headers={"x-powered-by": "Express"},
                cookies=["connect.sid"],
            ),
            "/api/": _probe(
                headers={"x-powered-by": "PHP/8.2.0"},
                cookies=["PHPSESSID"],
            ),
        })
        with patch(
            "apps.stubs.backend_hints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        techs = {f.data["technology"] for f in Finding.objects.all()}
        assert "Express" in techs
        assert "PHP" in techs


class NoMatchTests(TestCase):
    def test_empty_bundle_creates_no_findings(self) -> None:
        scan_run, target_run = _seed()
        with patch(
            "apps.stubs.backend_hints.runner.fetch_evidence",
            return_value=_bundle(),
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0

    def test_unknown_backend_creates_no_findings(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/": _probe(
                headers={"server": "nginx/1.24.0"},
                cookies=["random_session"],
                body="plain home",
            ),
        })
        with patch(
            "apps.stubs.backend_hints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0


class RegistryDispatchTests(TestCase):
    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.4")(run)

    def test_registered_under_1_4(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.4") is run
