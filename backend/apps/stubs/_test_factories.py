"""Shared test factories for stub runners.

Underscore prefix marks it as test-internal — production code MUST NOT
import this module. The factory creates a Project + ScanTarget + ScanRun
+ ScanTargetRun chain in one call so per-stub runner tests don't each
re-implement the seed.
"""
from __future__ import annotations

from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


def seed_target_run(
    *,
    stub_slug: str,
    host: str = "x.example",
    base_url: str | None = None,
    project_name: str = "acme",
) -> tuple[ScanRun, ScanTargetRun]:
    project = Project.objects.create(name=project_name)
    target = ScanTarget.objects.create(
        project=project,
        base_url=base_url or f"https://{host}",
        host=host,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug=stub_slug)
    target_run = ScanTargetRun.objects.create(
        scan_run=scan_run, target=target,
    )
    return scan_run, target_run
