"""Detection-path tests for stub 1.6 runner — soft-404 filter,
metadata extraction, meaningful-path filter."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.findings.models import Finding, FindingStatus, Severity

from ..runner import run

from ._runner_helpers import make_nonce_bundle, make_probe, seed_for_1_6


_seed = seed_for_1_6
_nonce_bundle = make_nonce_bundle
_probe = make_probe


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

        assert not Finding.objects.filter(data__path="/admin").exists()


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
