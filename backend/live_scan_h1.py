"""Live passive scan: well_known_paths (1.20) against 2 HackerOne targets.

Targets: hackerone/shopify (www.shopify.com) and
         hackerone/nextcloud (nextcloud.com)

Run inside the container:
  docker exec earn-money-backend-1 sh -c 'cd /app && python live_scan_h1.py'
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()  # triggers AppConfig.ready() which registers all runners

from unittest.mock import patch

from apps.evidence.models import Evidence
from apps.findings.models import Finding
from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.scans.tasks import _process_target_run
from apps.targets.models import ScanTarget

TARGETS = [
    ("shopify", "www.shopify.com", "https://www.shopify.com"),
    ("nextcloud", "nextcloud.com", "https://nextcloud.com"),
]

STUB_SLUG = "1.20"


def _seed(program_slug: str, host: str, base_url: str):
    project, _ = Project.objects.get_or_create(name=f"h1-{program_slug}")
    target, _ = ScanTarget.objects.get_or_create(
        project=project, host=host,
        defaults={"base_url": base_url},
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug=STUB_SLUG)
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return scan_run, target_run


def _run_one(program_slug: str, host: str, base_url: str) -> None:
    print(f"\n{'='*60}")
    print(f"Scanning: {base_url}  [{program_slug}]")
    print("="*60)

    scan_run, target_run = _seed(program_slug, host, base_url)

    with patch("apps.programs.flags.require_recon_enabled"):
        _process_target_run(scan_run, target_run)

    findings = Finding.objects.filter(scan_run=scan_run)
    if findings.exists():
        print(f"\nFindings ({findings.count()}):")
        for f in findings:
            print(f"  [{f.severity}] {f.category}: {f.data.get('path', f.data)}")
    else:
        print("\nNo findings.")

    ev_count = Evidence.objects.filter(scan_run=scan_run).count()
    print(f"Evidence rows: {ev_count}")


if __name__ == "__main__":
    for slug, host, url in TARGETS:
        _run_one(slug, host, url)

    print("\n\nDone.")
