"""Stub 2.8 runner — reset-poisoning.

Spec: docs/superpowers/specs/.../02-authentication/<spec>.md
Skeleton — registers with `@guarded_runner` and gates on RoE +
authorised test account + required fixture secret. Detection logic
lands when the fixture is provisioned per program.
"""
from __future__ import annotations

import os

from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal

from ..runners import guarded_runner


_FIXTURE_SECRET_ENV = "FIXTURE_MAILBOX_TOKEN"


@guarded_runner("2.8")
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    if not program.roe.allow_password_reset_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.8",
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_password_reset_probes"},
        )
        return

    if not program.roe.authorized_test_accounts:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.8",
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_authorized_test_accounts"},
        )
        return

    if not os.environ.get(_FIXTURE_SECRET_ENV):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.8",
            reason=RefusalReason.MISSING_SECRET,
            details={"missing_secret": _FIXTURE_SECRET_ENV},
        )
        return

    # Detection chain ships when the fixture is provisioned.
    return
