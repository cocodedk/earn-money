"""Live network tests for 1.9 old-endpoints.

OPT-IN — hits real target.cocode.dk fixtures. Run with:

    LIVE_TESTS=1 docker compose run --rm backend \\
        pytest apps/stubs/old_endpoints/tests/test_live_old_endpoints.py

Live reality on these fixtures (as of 2026-05-19):
- juiceshop.cocode.dk: SPA fallthrough returns the same index.html
  for every seeded legacy path. Baseline-body equality classifies
  them as generic_fallback. No Deprecation / Sunset headers on
  any endpoint. Zero findings.
- dvwa.cocode.dk: Most seeded paths 404; a handful return the
  DVWA index page (status 200, body == baseline) — generic_fallback.
  No deprecation headers. Zero findings.
- webgoat.cocode.dk: Root redirects to /WebGoat/login (302); seeded
  legacy paths return 404 from Tomcat. Zero findings.

The three "zero findings" assertions encode the lab-fixture reality
— they guard against future regressions of the baseline-body
fallback filter or noisy header false positives.
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
        stub_slug="1.9", host=host, base_url=f"https://{host}",
    )


class JuiceShopLiveTests(TestCase):
    def test_spa_fallthrough_yields_no_findings(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)
        assert Finding.objects.count() == 0


class DvwaLiveTests(TestCase):
    def test_no_deprecation_markers_yields_no_findings(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)
        assert Finding.objects.count() == 0


class WebGoatLiveTests(TestCase):
    def test_tomcat_404s_yield_no_findings(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)
        assert Finding.objects.count() == 0
