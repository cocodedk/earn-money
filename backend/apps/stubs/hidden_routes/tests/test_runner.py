"""End-to-end runner tests for stub 1.6 with mocked fetcher.

The runner builds a soft-404 profile from the two nonce probes, then
emits a Finding per probed path whose response body hash differs from
that profile. Robots.txt + sitemap.xml extracted candidates surface
as additional Findings (no follow-up fetch in MVP — they're recorded
as `disclosed routes`).
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
    return seed_target_run(stub_slug="1.6", host="x.example")


def _baseline(body: str = "welcome") -> dict:
    return {"status": 200, "body": body, "url": "https://x.example/"}


def _probe(body: str = "", status: int = 200) -> dict:
    return {"status": status, "body": body, "url": ""}


def _bundle(
    baseline: dict | None = None,
    probes: dict[str, dict] | None = None,
) -> dict:
    return {
        "baseline": baseline if baseline is not None else _baseline(),
        "probes": probes or {},
    }


def _nonce_bundle(
    nonce_body: str = "not found",
    nonce_status: int = 404,
    probes: dict[str, dict] | None = None,
) -> dict:
    base_probes = {
        "/.well-known/scanner_nonexistent_aaaaaaaa": _probe(
            nonce_body, nonce_status
        ),
        "/scanner_nonexistent_bbbbbbbb": _probe(nonce_body, nonce_status),
    }
    if probes:
        base_probes.update(probes)
    return _bundle(probes=base_probes)


class CommonPathDetectionTests(TestCase):
    def test_admin_distinct_from_soft_404_surfaces_finding(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="404 page", nonce_status=404,
            probes={"/admin": _probe("Admin Console <h1>", 200)},
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/admin")
        assert finding.severity == Severity.INFO
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["source"] == "hidden_routes"


class Soft404FilterTests(TestCase):
    def test_response_matching_soft_404_profile_suppressed(self) -> None:
        # Juice Shop pattern: every unknown path returns the SPA shell.
        # Both the nonce probes AND /admin return the same body. The
        # runner must NOT emit a finding for /admin in that case.
        scan_run, target_run = _seed()
        shell = "<!doctype html><app-root></app-root>"
        bundle = _nonce_bundle(
            nonce_body=shell, nonce_status=200,
            probes={"/admin": _probe(shell, 200)},
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        admin_findings = Finding.objects.filter(data__path="/admin")
        assert not admin_findings.exists()


class MetadataExtractionTests(TestCase):
    def test_robots_disallow_path_emitted_as_finding(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="404", nonce_status=404,
            probes={
                "/robots.txt": _probe(
                    "User-agent: *\nDisallow: /secret-admin\n", 200,
                ),
            },
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/secret-admin")
        assert finding.data["source_kind"] == "robots.txt"

    def test_sitemap_loc_emitted_as_finding(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="404", nonce_status=404,
            probes={
                "/sitemap.xml": _probe(
                    '<urlset><loc>https://x.example/secret-page</loc></urlset>',
                    200,
                ),
            },
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/secret-page")
        assert finding.data["source_kind"] == "sitemap.xml"


class MeaningfulPathFilterTests(TestCase):
    def test_root_disallow_filtered(self) -> None:
        # DVWA's robots.txt says `Disallow: /` — that's a deny-all
        # directive, not a disclosure of a hidden route. Filter it out.
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="404", nonce_status=404,
            probes={"/robots.txt": _probe("User-agent: *\nDisallow: /\n", 200)},
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/").exists()

    def test_root_loc_in_sitemap_filtered(self) -> None:
        # Sitemap declaring `<loc>/</loc>` is the homepage, not a
        # hidden route.
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="404", nonce_status=404,
            probes={
                "/sitemap.xml": _probe(
                    "<urlset><loc>/</loc></urlset>", 200,
                ),
            },
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/").exists()


class DedupTests(TestCase):
    def test_same_path_from_probe_and_metadata_collapses(self) -> None:
        # /admin appears both as a directly-probed 200 AND in robots.txt
        # Disallow — same path, one Finding.
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="404", nonce_status=404,
            probes={
                "/admin": _probe("Admin Console", 200),
                "/robots.txt": _probe("Disallow: /admin\n", 200),
            },
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        admin_findings = Finding.objects.filter(data__path="/admin")
        assert admin_findings.count() == 1


class ProbeStatus404Tests(TestCase):
    def test_404_status_skips_finding(self) -> None:
        # Some servers return a 404 with a body distinct from the soft-
        # 404 profile. 404 means "no resource here" regardless of
        # whether the body is distinctive — runner skips the path.
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="generic 404", nonce_status=404,
            probes={"/admin": _probe("custom 404 body", 404)},
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()


class NoBaselineTests(TestCase):
    def test_baseline_none_yields_no_findings(self) -> None:
        # Fetcher returned baseline=None → target unreachable. Runner
        # short-circuits.
        scan_run, target_run = _seed()
        bundle = {"baseline": None, "probes": {}}
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0


class NoMatchTests(TestCase):
    def test_all_probes_match_soft_404_yields_zero(self) -> None:
        scan_run, target_run = _seed()
        # All common-path probes return the same body as nonces.
        bundle = _nonce_bundle(nonce_body="<html>not found</html>", nonce_status=200)
        for path in ("/admin", "/login", "/api"):
            bundle["probes"][path] = _probe("<html>not found</html>", 200)
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0


class RegistryDispatchTests(TestCase):
    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.6")(run)

    def test_registered_under_1_6(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.6") is run
