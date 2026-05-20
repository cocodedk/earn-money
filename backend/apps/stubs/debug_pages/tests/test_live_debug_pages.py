"""Live network tests for 1.10 debug-pages.

OPT-IN — hits real target.cocode.dk fixtures. Run with:

    LIVE_TESTS=1 docker compose exec backend \\
        pytest apps/stubs/debug_pages/tests/test_live_debug_pages.py

Live reality on these fixtures (as of 2026-05-19):
- juiceshop.cocode.dk: Node/Express SPA. Seeded paths either 404
  or return the SPA index (200 with body == baseline) — the
  generic_fallback filter rejects them. 0 findings.
- dvwa.cocode.dk: PHP/Apache. /server-status and /server-status/
  return 403 (Apache mod_status enabled but ACL'd to localhost).
  Classifier correctly labels both as apache_server_status /
  blocked / candidate / medium — the spec's "debug-looking path
  is blocked but clearly exists" rule firing on real data. 2
  candidate findings, not a regression.
- webgoat.cocode.dk: Java/Tomcat. /actuator and /debug paths
  return Tomcat 404. 0 findings.

Juice Shop and WebGoat assert zero-findings — guards FP shapes
the stub has to resist (SPA fallthrough; Tomcat 404). DVWA asserts
the shape of any findings rather than a count — confirms the
classifier vocabulary is intact.
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
        stub_slug="1.10", host=host, base_url=f"https://{host}",
    )


class JuiceShopLiveTests(TestCase):
    def test_spa_fallthrough_yields_no_findings(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)
        # Juice Shop Express returns its SPA index for unknown paths;
        # the baseline-body equality filter (in classify) must reject
        # them as generic_fallback.
        assert Finding.objects.filter(scan_run=scan_run).count() == 0


class DvwaLiveTests(TestCase):
    def test_dvwa_findings_carry_valid_kind_and_exposure(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)
        # DVWA may legitimately expose phpinfo or other debug pages
        # depending on the image. Validate shape of any findings
        # rather than asserting count.
        valid_kinds = {
            "phpinfo", "environment_leak", "stack_trace",
            "apache_server_status", "apache_server_info",
            "spring_actuator", "go_pprof",
            "symfony_profiler", "django_debug_toolbar",
            "werkzeug_debugger", "laravel_telescope",
            "laravel_horizon", "laravel_ignition", "rails_info",
        }
        for finding in Finding.objects.filter(scan_run=scan_run):
            assert finding.data["kind"] in valid_kinds, (
                f"Unknown kind in finding: {finding.data}"
            )
            assert finding.data["exposure"] in {
                "public", "blocked", "login_required",
                "redirected", "unknown",
            }


class WebGoatLiveTests(TestCase):
    def test_tomcat_404s_yield_no_findings(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)
        # WebGoat root redirects to /WebGoat/login; Tomcat 404s the
        # seeded debug paths. Zero findings expected.
        assert Finding.objects.filter(scan_run=scan_run).count() == 0
