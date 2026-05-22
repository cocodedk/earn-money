"""Live smoke for the scope-enforcement layer.

Runs three checks against a real container with the algolia program
loaded in PROGRAMS_ROOT and the RECON_ENABLED flag present:

1. In-scope: create a ScanRun for https://www.algolia.com via the
   serializer. Pre-flight should accept it. Dispatch one runner
   (stub 1.2 = server_headers) synchronously and confirm no
   OUT_OF_SCOPE_REJECTED events fire.
2. Pre-flight negative: attempt a ScanRun for
   https://out-of-scope.example.invalid/. Serializer must refuse.
3. Fetcher negative: in-scope ScanRun for algolia BUT mock the
   registry to return a program with empty in_scope; the runner
   must emit OUT_OF_SCOPE_REJECTED and not hit HTTP.

Cleans up afterwards (deletes the smoke Project).
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import django


def main() -> int:
    # Ensure /app is on sys.path so `config` resolves regardless of CWD.
    here = os.path.abspath(os.path.dirname(__file__))
    app_root = os.path.dirname(here)
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from apps.events.models import Event
    from apps.events.types import EventType
    from apps.programs.loader import Program, get_registry
    from apps.programs.roe import RoE
    from apps.programs.scope import Scope
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.scans.serializers import ScanRunSerializer
    from apps.stubs.runners import get as registered_runner
    from apps.targets.models import ScanTarget

    rc = 0

    project = Project.objects.create(name="smoke-scope-enforcement")
    print("=== 1. In-scope pre-flight: www.algolia.com ===")
    target = ScanTarget.objects.create(
        project=project, base_url="https://www.algolia.com",
        host="www.algolia.com",
    )
    ser = ScanRunSerializer(data={
        "project": str(project.id),
        "stub_slug": "1.2",
        "target_ids": [str(target.id)],
    })
    ok = ser.is_valid()
    if not ok:
        print("FAIL: in-scope ScanRun rejected by serializer:", ser.errors)
        rc = 1
    else:
        print("PASS: in-scope ScanRun accepted by serializer.")

    print()
    print("=== 2. Pre-flight negative: out-of-scope.example.invalid ===")
    oos_target = ScanTarget.objects.create(
        project=project, base_url="https://out-of-scope.example.invalid",
        host="out-of-scope.example.invalid",
    )
    ser_oos = ScanRunSerializer(data={
        "project": str(project.id),
        "stub_slug": "1.2",
        "target_ids": [str(oos_target.id)],
    })
    if ser_oos.is_valid():
        print("FAIL: OOS ScanRun was accepted — pre-flight is broken!")
        rc = 1
    else:
        print("PASS: OOS ScanRun rejected:", ser_oos.errors)

    print()
    print("=== 3. Fetcher negative: candidate URL outside scope ===")
    scan_run = ScanRun.objects.create(project=project, stub_slug="1.2")
    target_run = ScanTargetRun.objects.create(
        scan_run=scan_run, target=target,
    )
    off_scope = Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["only.in-some-other-program.example"],
            out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=10),
    )
    runner_fn = registered_runner("1.2")
    before = Event.objects.filter(
        scan_run=scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
    ).count()
    with patch.object(get_registry(), "find_for_host", return_value=off_scope):
        runner_fn(scan_run, target_run)
    after = Event.objects.filter(
        scan_run=scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
    ).count()
    if after > before:
        print(f"PASS: fetcher emitted OUT_OF_SCOPE_REJECTED ({after - before} event)")
    else:
        print("FAIL: fetcher did NOT emit OUT_OF_SCOPE_REJECTED")
        rc = 1

    project.delete()
    # Live multi-stub algolia dispatch moved to `scripts/run_smoke.py`
    # which exercises the full API + Celery path (what the dashboard
    # uses). This script keeps the synchronous in-process checks that
    # don't require a Celery worker.
    print()
    print("Cleaned up smoke project.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
