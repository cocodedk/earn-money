"""Live network tests for 1.3 frontend-framework.

OPT-IN — hits real target.cocode.dk fixtures over HTTPS. Run with:

    LIVE_TESTS=1 docker compose run --rm backend \\
        pytest apps/stubs/frontend_framework/tests/test_live_frontend_framework.py

Live reality on these fixtures (as of 2026-05-19, after fetching base
+ same-origin assets):
- juiceshop.cocode.dk: Angular SPA. Body has `<app-root>`; static HTML
  doesn't have `ng-version` (set at runtime). Expect: Angular.
- dvwa.cocode.dk: plain PHP login page; no frontend framework. Expect:
  zero Findings — this is intentional and verifies the no-match path
  end-to-end against a real target.
- webgoat.cocode.dk: WebGoat login page loads Bootstrap CSS. Expect:
  Bootstrap.

Skipped by default; excluded from the strict-coverage bar via the
`*/test_live_*.py` omit pattern.
"""
from __future__ import annotations

import os

import pytest
from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.confidence import CONFIDENCE_RANK, confidence_rank
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
        stub_slug="1.3", host=host, base_url=f"https://{host}",
    )


def _assert_medium_or_higher(findings) -> None:
    medium = CONFIDENCE_RANK["medium"]
    for finding in findings:
        assert confidence_rank(finding.confidence) >= medium, (
            f"finding {finding.id} has confidence={finding.confidence}; "
            f"spec requires medium or higher"
        )


class JuiceShopLiveTests(TestCase):
    def test_detects_angular(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        techs = {f.data["technology"] for f in findings}
        assert "Angular" in techs, (
            f"juiceshop.cocode.dk expected Angular; got {techs}"
        )
        assert Evidence.objects.count() >= 1
        _assert_medium_or_higher(findings)


class DvwaLiveTests(TestCase):
    def test_no_frontend_framework_on_login_page(self) -> None:
        # DVWA's unauthenticated landing page is a plain PHP login form
        # — no SPA framework. The runner is correct to emit zero
        # Findings here; this test guards against a noisy false-positive
        # signature being added later.
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        assert findings == [], (
            f"dvwa.cocode.dk expected no findings on the login page; "
            f"got {[f.data['technology'] for f in findings]}"
        )


class WebGoatLiveTests(TestCase):
    def test_detects_bootstrap(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        techs = {f.data["technology"] for f in findings}
        assert "Bootstrap" in techs, (
            f"webgoat.cocode.dk expected Bootstrap; got {techs}"
        )
        assert Evidence.objects.count() >= 1
        _assert_medium_or_higher(findings)
