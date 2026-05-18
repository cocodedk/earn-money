"""Live network tests for 1.2 server-headers.

OPT-IN — hits real target.cocode.dk fixtures over HTTPS. Run with:

    LIVE_TESTS=1 docker compose run --rm backend \\
        pytest apps/stubs/server_headers/tests/test_live_server_headers.py

Skipped by default and excluded from the strict-coverage bar via
`*/test_live_*.py` in pyproject.toml. See stub 1.1's
test_live_framework_detection for the established pattern.

Live header reality on these fixtures (Caddy reverse-proxies all three):
- juiceshop.cocode.dk: only `Via: 1.1 Caddy` (Caddy strips upstream
  Server). Expect: caddy.
- dvwa.cocode.dk: Apache/<v> + PHP/<v> + Via: 1.1 Caddy. Expect:
  apache_httpd + php + caddy.
- webgoat.cocode.dk: only `Via: 1.1 Caddy` (Tomcat upstream Server
  also stripped). Expect: caddy.
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
        stub_slug="1.2", host=host, base_url=f"https://{host}",
    )


def _assert_medium_or_higher(findings) -> None:
    medium = CONFIDENCE_RANK["medium"]
    for finding in findings:
        assert confidence_rank(finding.confidence) >= medium, (
            f"finding {finding.id} has confidence={finding.confidence}; "
            f"spec requires medium or higher"
        )


class JuiceShopLiveTests(TestCase):
    def test_detects_caddy_through_proxy(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        techs = {f.data["technology"] for f in findings}
        assert "caddy" in techs, (
            f"juiceshop.cocode.dk expected caddy; got {techs}"
        )
        assert Evidence.objects.count() >= 1
        _assert_medium_or_higher(findings)


class DvwaLiveTests(TestCase):
    def test_detects_apache_php_and_caddy(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        techs = {f.data["technology"] for f in findings}
        # Apache + PHP come from the upstream (DVWA's own stack);
        # caddy comes from the Via header injected by the reverse proxy.
        assert "apache_httpd" in techs, f"got {techs}"
        assert "php" in techs, f"got {techs}"
        assert "caddy" in techs, f"got {techs}"
        # Version extraction sanity-check — Apache/PHP signatures both
        # carry version_regex.
        apache_finding = Finding.objects.get(data__technology="apache_httpd")
        assert apache_finding.data["version"] is not None
        php_finding = Finding.objects.get(data__technology="php")
        assert php_finding.data["version"] is not None
        _assert_medium_or_higher(findings)


class WebGoatLiveTests(TestCase):
    def test_detects_caddy_through_proxy(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        techs = {f.data["technology"] for f in findings}
        assert "caddy" in techs, (
            f"webgoat.cocode.dk expected caddy; got {techs}"
        )
        assert Evidence.objects.count() >= 1
        _assert_medium_or_higher(findings)
