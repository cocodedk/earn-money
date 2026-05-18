"""Live network tests for 1.1 framework-detection.

OPT-IN — these hit real target.cocode.dk fixtures over HTTPS. The
target host runs Juice Shop, DVWA, and WebGoat behind Caddy and is
explicitly authorised for any HTTP technique (see CLAUDE.md → Test
fixtures). Outside that host these tests should NOT run.

Run with:

    LIVE_TESTS=1 docker compose run --rm backend \\
        pytest apps/stubs/framework_detection/tests/test_live_framework_detection.py

Skipped by default and excluded from the strict-coverage bar via
`*/test_live_*.py` in pyproject.toml — so the CI bar still passes on
networks that can't reach target.cocode.dk.
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


def _setup_run(base_url: str, host: str) -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(
        stub_slug="1.1",
        host=host,
        base_url=base_url,
        project_name=f"live-{host}",
    )


def _assert_medium_or_higher(findings) -> None:
    medium = CONFIDENCE_RANK["medium"]
    for finding in findings:
        assert confidence_rank(finding.confidence) >= medium, (
            f"finding {finding.id} has confidence={finding.confidence}; "
            f"spec requires medium or higher"
        )


class JuiceShopLiveTests(TestCase):
    def test_detects_juice_shop_and_angular(self) -> None:
        scan_run, target_run = _setup_run(
            "https://juiceshop.cocode.dk", "juiceshop.cocode.dk",
        )
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        techs = {f.data["technology"] for f in findings}
        # Cookbook 1.1 acceptance: Juice Shop fixture must surface as
        # either the product marker or an Angular SPA signal.
        assert techs & {"OWASP Juice Shop", "Angular SPA"}, (
            f"juiceshop.cocode.dk produced no expected tech (got {techs})"
        )
        assert Evidence.objects.count() >= 1
        _assert_medium_or_higher(findings)


class DvwaLiveTests(TestCase):
    def test_detects_php_or_dvwa_marker(self) -> None:
        scan_run, target_run = _setup_run(
            "https://dvwa.cocode.dk", "dvwa.cocode.dk",
        )
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        techs = {f.data["technology"] for f in findings}
        assert techs & {"PHP", "DVWA"}, (
            f"dvwa.cocode.dk produced no expected tech (got {techs})"
        )
        assert Evidence.objects.count() >= 1
        _assert_medium_or_higher(findings)


class WebGoatLiveTests(TestCase):
    def test_detects_java_or_webgoat_marker(self) -> None:
        scan_run, target_run = _setup_run(
            "https://webgoat.cocode.dk", "webgoat.cocode.dk",
        )
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        techs = {f.data["technology"] for f in findings}
        assert techs & {"Java Servlet", "WebGoat"}, (
            f"webgoat.cocode.dk produced no expected tech (got {techs})"
        )
        assert Evidence.objects.count() >= 1
        _assert_medium_or_higher(findings)
