"""Live network tests for 1.8 admin-panels.

OPT-IN — hits real target.cocode.dk fixtures. Run with:

    LIVE_TESTS=1 docker compose run --rm backend \\
        pytest apps/stubs/admin_panels/tests/test_live_admin_panels.py

Live reality on these fixtures (as of 2026-05-19):
- juiceshop.cocode.dk: SPA fallthrough returns 200 + index.html for
  every candidate path AND the soft-404 nonces. Hash-based soft-404
  filter suppresses all candidates. Static HTML has no
  password-form/admin-panel markers, so no body-marker override.
  Zero findings.
- dvwa.cocode.dk: 404s for all candidate paths. Zero findings.
- webgoat.cocode.dk: 404s for all candidate paths (Tomcat default
  404 page). Zero findings.

All three "zero findings" assertions encode the lab-fixture reality
— they guard against future regressions of the soft-404 filter or
noisy body-marker false positives.
"""
from __future__ import annotations

import os

import pytest
from django.test import TestCase

from apps.findings.models import Finding
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run

from ..runner import run


pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE_TESTS") != "1",
    reason="LIVE_TESTS=1 required to opt into network-dependent fixtures",
)


def _seed(host: str) -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(
        stub_slug="1.8", host=host, base_url=f"https://{host}",
    )


class JuiceShopLiveTests(TestCase):
    def test_spa_fallthrough_filtered(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)
        assert Finding.objects.count() == 0


class DvwaLiveTests(TestCase):
    def test_404_responses_produce_no_findings(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)
        assert Finding.objects.count() == 0


class WebGoatLiveTests(TestCase):
    def test_404_responses_produce_no_findings(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)
        assert Finding.objects.count() == 0
