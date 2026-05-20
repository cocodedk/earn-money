"""Live network tests for 1.12 sitemap-xml.

OPT-IN — hits real target.cocode.dk fixtures. Run with:

    LIVE_TESTS=1 docker compose exec backend \\
        pytest apps/stubs/sitemap_xml/tests/test_live_sitemap_xml.py

Assertions pin shape (classification in the spec's closed set,
counts are non-negative ints, expected data keys present), not
specific values — fixture sitemaps may legitimately change.
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


_VALID_CLASSIFICATIONS = {
    "sitemap_present", "sitemap_index_present",
    "sitemap_parse_error", "sitemap_too_large",
    "sitemap_fetch_error", "protected", "not_found",
    "client_error",
}
_VALID_STATUSES = {
    FindingStatus.CONFIRMED, FindingStatus.CANDIDATE,
    FindingStatus.REJECTED,
}


def _seed(host: str) -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(
        stub_slug="1.12", host=host, base_url=f"https://{host}",
    )


class JuiceShopLiveTests(TestCase):
    def test_juiceshop_sitemap_finding_shape(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] == "sitemap_xml"
        assert finding.data["classification"] in _VALID_CLASSIFICATIONS
        assert finding.status in _VALID_STATUSES
        assert isinstance(finding.data["extracted_url_count"], int)
        assert finding.data["extracted_url_count"] >= 0


class DvwaLiveTests(TestCase):
    def test_dvwa_sitemap_finding_shape(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["classification"] in _VALID_CLASSIFICATIONS
        # When sitemap is absent, in_scope_url_count must be 0.
        if finding.data["classification"] == "not_found":
            assert finding.data["in_scope_url_count"] == 0


class WebGoatLiveTests(TestCase):
    def test_webgoat_sitemap_finding_shape(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] == "sitemap_xml"
        assert finding.data["classification"] in _VALID_CLASSIFICATIONS
