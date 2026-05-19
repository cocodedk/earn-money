"""Tests for stub 1.11 runner.run — fetch + parse + classify +
persist with mocked HTTP.
"""
from __future__ import annotations

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus
from apps.stubs._test_factories import seed_target_run

from ..runner import run
from ._helpers import mocked_fetcher, resp


def _seed():
    return seed_target_run(stub_slug="1.11")


class RunnerPresentTests(TestCase):
    def test_200_robots_with_disallows_writes_finding(self) -> None:
        scan_run, target_run = _seed()
        body = (
            "User-agent: *\n"
            "Disallow: /admin\n"
            "Disallow: /backup.zip\n"
            "Allow: /assets/\n"
            "Sitemap: https://x.example/sitemap.xml"
        )
        with mocked_fetcher({"/robots.txt": resp(body, status_code=200)}):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        data = finding.data
        assert data["finding_type"] == "robots_txt"
        assert data["classification"] == "present"
        assert data["disallowed_paths_count"] == 2
        assert data["allowed_paths_count"] == 1
        assert data["sitemaps_count"] == 1
        # Both /admin and /backup.zip have sensitive tokens.
        assert data["sensitive_path_hints_count"] == 2
        assert "/admin" in data["same_origin_path_hints"]

    def test_evidence_row_linked_to_finding(self) -> None:
        scan_run, target_run = _seed()
        body = "User-agent: *\nDisallow: /admin"
        with mocked_fetcher({"/robots.txt": resp(body, status_code=200)}):
            run(scan_run, target_run)
        evidence = Evidence.objects.get(scan_run=scan_run)
        assert evidence.url.endswith("/robots.txt")
        finding = Finding.objects.get(scan_run=scan_run)
        assert str(evidence.id) in finding.data["evidence_ids"]


class RunnerEmptyTests(TestCase):
    def test_empty_body_writes_confirmed_empty_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({"/robots.txt": resp("", status_code=200)}):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.data["classification"] == "empty"
        assert finding.data["disallowed_paths_count"] == 0


class RunnerProtectedTests(TestCase):
    def test_403_writes_candidate_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({"/robots.txt": resp("", status_code=403)}):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["classification"] == "protected"


class RunnerNotFoundTests(TestCase):
    def test_404_writes_rejected_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({"/robots.txt": resp("", status_code=404)}):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.REJECTED
        assert finding.data["classification"] == "not_found"

    def test_evidence_still_persisted_on_404(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({"/robots.txt": resp("", status_code=404)}):
            run(scan_run, target_run)
        # Spec §Pass/fail rule 3 + §Evidence requirements: persist
        # Evidence even when the result is rejected.
        assert Evidence.objects.filter(scan_run=scan_run).count() == 1


class RunnerUnreachableTests(TestCase):
    def test_transport_error_writes_rejected_finding_with_no_body(
        self,
    ) -> None:
        import httpx
        scan_run, target_run = _seed()

        def raise_(_url, **_kwargs):
            raise httpx.ConnectError("DNS timeout")

        with mocked_fetcher(get_side_effect=raise_):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.REJECTED
        assert finding.data["classification"] == "unreachable"


class RunnerSitemapOriginTests(TestCase):
    def test_cross_origin_sitemap_categorized_separately(self) -> None:
        scan_run, target_run = _seed()
        body = (
            "User-agent: *\n"
            "Disallow: /admin\n"
            "Sitemap: https://x.example/site-a.xml\n"
            "Sitemap: https://other.example/site-b.xml"
        )
        with mocked_fetcher({"/robots.txt": resp(body, status_code=200)}):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["same_origin_sitemaps"] == [
            "https://x.example/site-a.xml",
        ]
        assert finding.data["cross_origin_sitemaps"] == [
            "https://other.example/site-b.xml",
        ]


class RunnerParseWarningTests(TestCase):
    def test_unknown_directive_recorded_as_warning(self) -> None:
        scan_run, target_run = _seed()
        body = (
            "User-agent: *\n"
            "Disallow: /admin\n"
            "Goofy-Directive: nope"
        )
        with mocked_fetcher({"/robots.txt": resp(body, status_code=200)}):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert any(
            "goofy-directive" in w.lower()
            for w in finding.data["parse_warnings"]
        )


class RunnerRegistrationTests(TestCase):
    def setUp(self) -> None:
        import importlib
        from apps.stubs.robots_txt import runner as runner_module
        importlib.reload(runner_module)

    def test_runner_registered_under_1_11(self) -> None:
        from apps.stubs.runners import _REGISTRY
        assert "1.11" in _REGISTRY
        assert callable(_REGISTRY["1.11"])
