"""Live network tests for 1.4 backend-hints.

OPT-IN — hits real target.cocode.dk fixtures. Run with:

    LIVE_TESTS=1 docker compose run --rm backend \\
        pytest apps/stubs/backend_hints/tests/test_live_backend_hints.py

Live reality on these fixtures (as of 2026-05-19):
- juiceshop.cocode.dk: Caddy reverse-proxies an Express backend, but
  strips the upstream `X-Powered-By: Express` header AND doesn't set
  the `connect.sid` cookie on the unauthenticated landing page. No
  reliable backend hint reaches us. Test expects zero findings.
- dvwa.cocode.dk: passes `X-Powered-By: PHP/<version>` through Caddy.
  Expect: PHP detected, with version extracted from the header.
- webgoat.cocode.dk: /api/ + the random-404 probe both surface the
  Apache Tomcat default error page (Tomcat generates these directly,
  before the Spring app sees them). Expect: Apache Tomcat detected
  via the body signature.

The juiceshop "expect zero findings" assertion is structurally
informative: it documents that a target running behind a header-
stripping reverse proxy is invisible to this stub's passive probes
— a real operational caveat worth encoding in the test suite.
"""
from __future__ import annotations

import os

import pytest
from django.test import TestCase

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
        stub_slug="1.4", host=host, base_url=f"https://{host}",
    )


def _assert_medium_or_higher(findings) -> None:
    medium = CONFIDENCE_RANK["medium"]
    for finding in findings:
        assert confidence_rank(finding.confidence) >= medium


class JuiceShopLiveTests(TestCase):
    def test_caddy_strips_express_signals(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)

        findings = list(Finding.objects.all())
        assert findings == [], (
            f"juiceshop.cocode.dk expected zero findings (Caddy strips "
            f"upstream backend signals); got "
            f"{[f.data['technology'] for f in findings]}"
        )


class DvwaLiveTests(TestCase):
    def test_detects_php_with_version(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="PHP")
        assert finding.confidence == "high"
        assert finding.data["version"] is not None
        _assert_medium_or_higher([finding])


class WebGoatLiveTests(TestCase):
    def test_detects_tomcat_via_error_page(self) -> None:
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)

        finding = Finding.objects.get(data__technology="Apache Tomcat")
        assert finding.data["technology_category"] == "app_runtime"
        _assert_medium_or_higher([finding])
