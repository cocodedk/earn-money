"""Live end-to-end smoke for stub 2.5 against the reset-canary fixture.

Operator runs this once after standing up the fixture stack to confirm
the chain wires together. The script bypasses Celery (calls the
runner inline) so a one-shot env override is enough:

    docker compose up -d mailpit reset-canary
    docker compose exec \\
        -e FIXTURE_MAILBOX_BACKEND=mailpit \\
        -e FIXTURE_MAILBOX_MAILPIT_URL=http://mailpit:8025 \\
        backend python scripts/smoke_reset_canary.py

Path exercised:
    1. Create an ephemeral Project + ScanTarget for reset-canary.
    2. Invoke the registered stub 2.5 runner directly with the seeded
       (scan_run, target_run) so the env-set mailbox backend is used.
    3. Confirm: at least one Finding with category=
       auth_predictable_reset_token landed, and an AUTH_FINDING_CANDIDATE
       event was emitted.

Exit 0 on success, 1 on any deviation (with a one-line diagnosis).
"""
from __future__ import annotations

import os
import sys

import django


_TARGET_URL = os.environ.get(
    "RESET_CANARY_URL", "http://reset-canary:3000",
)
_TARGET_HOST = "reset-canary"
_STUB = "2.5"


def _ensure_django() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    app_root = os.path.dirname(here)
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


_ensure_django()
from apps.events.models import Event  # noqa: E402
from apps.events.types import EventType  # noqa: E402
from apps.findings.models import Finding  # noqa: E402
from apps.programs.loader import get_registry  # noqa: E402
from apps.programs.preflight import host_from_url  # noqa: E402
from apps.projects.models import Project  # noqa: E402
from apps.scans.models import ScanRun, ScanTargetRun  # noqa: E402
from apps.stubs.predictable_reset_token.runner import run  # noqa: E402
from apps.targets.models import ScanTarget  # noqa: E402


def main() -> int:
    print(f"[smoke] target = {_TARGET_URL}  stub = {_STUB}")
    project = Project.objects.create(name="smoke-reset-canary")
    target = ScanTarget.objects.create(
        project=project, base_url=_TARGET_URL, host=_TARGET_HOST,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug=_STUB)
    target_run = ScanTargetRun.objects.create(
        scan_run=scan_run, target=target,
    )
    print(f"[smoke] host_from_url(target.base_url)={host_from_url(target.base_url)}")
    print(f"[smoke] env FIXTURE_MAILBOX_BACKEND={os.environ.get('FIXTURE_MAILBOX_BACKEND')}")
    print(f"[smoke] env FIXTURE_MAILBOX_MAILPIT_URL={os.environ.get('FIXTURE_MAILBOX_MAILPIT_URL')}")
    try:
        prog = get_registry().find_for_host(host_from_url(target.base_url))
        print(f"[smoke] program found: {prog.platform}/{prog.slug}, allow_password_reset_probes={prog.roe.allow_password_reset_probes}, authorized_test_accounts={prog.roe.authorized_test_accounts}")
    except Exception as e:
        print(f"[smoke] program lookup error: {type(e).__name__}: {e}")
    try:
        print("[smoke] invoking runner inline (bypassing Celery)...")
        run(scan_run, target_run)
        findings = list(Finding.objects.filter(
            scan_run=scan_run, category="auth_predictable_reset_token",
        ))
        events = list(Event.objects.filter(
            scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
        ))
        refusals = list(Event.objects.filter(scan_run=scan_run))
        print(f"[smoke] findings(predictable_reset_token) = {len(findings)}")
        print(f"[smoke] events(AUTH_FINDING_CANDIDATE)    = {len(events)}")
        print(f"[smoke] events(all)                       = {len(refusals)}")
        for r in refusals:
            print(f"  event: type={r.type} data={r.data}")
        if not findings:
            print("FAIL: no auth_predictable_reset_token Finding emitted")
            return 1
        if not events:
            print("FAIL: no AUTH_FINDING_CANDIDATE event emitted")
            return 1
        print("OK: chain fires end-to-end — Finding + event landed.")
        return 0
    finally:
        target_run.delete()
        scan_run.delete()
        target.delete()
        project.delete()


if __name__ == "__main__":
    sys.exit(main())
