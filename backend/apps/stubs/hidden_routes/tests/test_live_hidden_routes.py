"""Live network tests for 1.6 hidden-routes.

OPT-IN — hits real target.cocode.dk fixtures. Run with:

    LIVE_TESTS=1 docker compose run --rm backend \\
        pytest apps/stubs/hidden_routes/tests/test_live_hidden_routes.py

Live reality on these fixtures (as of 2026-05-19):
- juiceshop.cocode.dk: SPA fallthrough returns 200 + index.html for
  every unknown path; soft-404 filter drops /admin, /login, etc.
  /api and /api/v1 return 500 with distinct bodies (Express upstream
  errors past Caddy) — those DO surface as findings. /robots.txt
  exposes Disallow: /ftp → /ftp surfaces too.
- dvwa.cocode.dk: most common paths 404; /docs returns 403 with a
  distinct body and surfaces. robots.txt says Disallow: / (deny-all)
  which the meaningful-path filter drops.
- webgoat.cocode.dk: all common paths 404 + Tomcat returns 404 HTML
  for /robots.txt and /sitemap.xml too — zero findings.
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
        stub_slug="1.6", host=host, base_url=f"https://{host}",
    )


class JuiceShopLiveTests(TestCase):
    def test_surfaces_api_and_ftp(self) -> None:
        scan_run, target_run = _seed("juiceshop.cocode.dk")
        run(scan_run, target_run)

        paths = {f.data["path"] for f in Finding.objects.all()}
        # /api and /api/v1 return 500 with distinct bodies — Express
        # backend errors that the SPA-shell soft-404 filter doesn't
        # match.
        assert "/api" in paths
        # /ftp from robots.txt Disallow.
        assert "/ftp" in paths


class DvwaLiveTests(TestCase):
    def test_surfaces_docs_path(self) -> None:
        scan_run, target_run = _seed("dvwa.cocode.dk")
        run(scan_run, target_run)

        paths = {f.data["path"] for f in Finding.objects.all()}
        # /docs returns 403 with a distinct body — not soft-404.
        assert "/docs" in paths
        # robots.txt Disallow: / would otherwise add "/" — meaningful-
        # path filter must keep it out.
        assert "/" not in paths


class WebGoatLiveTests(TestCase):
    def test_zero_findings(self) -> None:
        # Tomcat 404s every common path + the metadata files too;
        # the soft-404 filter drops every candidate.
        scan_run, target_run = _seed("webgoat.cocode.dk")
        run(scan_run, target_run)
        assert Finding.objects.count() == 0
