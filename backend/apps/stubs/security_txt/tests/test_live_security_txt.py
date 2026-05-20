"""Live network tests for 1.13 security-txt.

OPT-IN — hits real target.cocode.dk fixtures. Run with:

    LIVE_TESTS=1 docker compose exec backend \\
        pytest apps/stubs/security_txt/tests/test_live_security_txt.py

Assertions pin shape (finding_type in the spec's 10-value closed
set, finding.status in the FindingStatus enum), not specific
values — fixture security.txt presence may change.
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


_VALID_FINDING_TYPES = {
    "missing_security_txt", "blocked_security_txt",
    "malformed_security_txt", "security_txt_no_contact",
    "security_txt_expired", "security_txt_missing_expires",
    "security_txt_canonical_mismatch", "security_txt_legacy_only",
    "security_txt_conflicting_files", "security_txt_present_valid",
}
_VALID_STATUSES = {
    FindingStatus.CONFIRMED, FindingStatus.CANDIDATE,
    FindingStatus.REJECTED,
}


def _seed(host: str) -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(
        stub_slug="1.13", host=host, base_url=f"https://{host}",
    )


class JuiceShopLiveTests(TestCase):
    def test_juiceshop_finding_shape(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] in _VALID_FINDING_TYPES
        assert finding.status in _VALID_STATUSES
        assert "canonical_kind" in finding.data
        assert "legacy_kind" in finding.data


class DvwaLiveTests(TestCase):
    def test_dvwa_finding_shape(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] in _VALID_FINDING_TYPES


class WebGoatLiveTests(TestCase):
    def test_webgoat_finding_shape(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] in _VALID_FINDING_TYPES
