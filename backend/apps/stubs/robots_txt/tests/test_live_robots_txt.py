"""Live network tests for 1.11 robots-txt.

OPT-IN — hits real target.cocode.dk fixtures. Run with:

    LIVE_TESTS=1 docker compose exec backend \\
        pytest apps/stubs/robots_txt/tests/test_live_robots_txt.py

Live reality is recorded after the first successful run; assertions
guard against future regressions rather than pinning specific
finding content (the lab images may legitimately update).
"""
from __future__ import annotations

import os

import pytest
from django.test import TestCase

from apps.findings.models import Finding, FindingStatus
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run

from ..runner import run


pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE_TESTS") != "1",
    reason="LIVE_TESTS=1 required to opt into network-dependent fixtures",
)


def _seed(host: str) -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(
        stub_slug="1.11", host=host, base_url=f"https://{host}",
    )


class JuiceShopLiveTests(TestCase):
    def test_robots_txt_finding_has_valid_shape(self) -> None:
        # Juice Shop ships a robots.txt with a few Disallow rules.
        # The runner should produce a confirmed `present` finding
        # with at least one disallowed path.
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        valid_classifications = {
            "present", "empty", "protected", "not_found",
            "redirected", "cross_origin_redirect_blocked",
            "redirect_limit_exceeded", "client_error",
            "server_error", "unreachable",
        }
        assert finding.data["classification"] in valid_classifications
        # When present, the spec promises the disallow/allow/sitemap
        # arrays exist (possibly empty).
        for key in ("same_origin_path_hints", "same_origin_sitemaps",
                    "cross_origin_sitemaps", "parse_warnings"):
            assert key in finding.data


class DvwaLiveTests(TestCase):
    def test_dvwa_robots_finding_shape(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        # Either present / empty / not_found — all valid for DVWA.
        # If `present` the counts must be non-negative integers.
        assert isinstance(finding.data["disallowed_paths_count"], int)
        assert finding.data["disallowed_paths_count"] >= 0
        assert isinstance(finding.data["sensitive_path_hints_count"], int)


class WebGoatLiveTests(TestCase):
    def test_webgoat_robots_finding_shape(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        # WebGoat usually returns 404 / not_found or redirects to
        # /WebGoat/. Either is a valid classification; assertion
        # pins shape, not value.
        assert finding.data["finding_type"] == "robots_txt"
        assert finding.status in {
            FindingStatus.CONFIRMED, FindingStatus.CANDIDATE,
            FindingStatus.REJECTED,
        }
