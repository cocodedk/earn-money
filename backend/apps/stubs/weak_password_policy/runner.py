"""Stub 2.2 runner — weak password policy detection.

Spec: docs/superpowers/specs/.../02-authentication/02-weak-password-policy.md

Detection requires a scanner-owned canary account on the target (the
runner submits progressively weaker passwords against a password-change
flow). That fixture is per-program: the operator pre-registers a test
account, stores the password in `FIXTURE_TEST_PASSWORD` env var, adds
the account identifier to `roe.md::authorized_test_accounts`, and
flips `allow_active_login_probes=True`.

Until fixture provisioning lands, this stub emits
`AUTH_FIXTURE_REQUIRED` with the env-var name so the operator knows
exactly what to set up. The full submit + classify chain ships when
the first fixture is provisioned.
"""
from __future__ import annotations

import os

from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal

from ..runners import guarded_runner


_FIXTURE_PASSWORD_ENV = "FIXTURE_TEST_PASSWORD"


@guarded_runner("2.2")
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    if not program.roe.allow_active_login_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.2",
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_active_login_probes"},
        )
        return

    if not program.roe.authorized_test_accounts:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.2",
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_authorized_test_accounts"},
        )
        return

    if not os.environ.get(_FIXTURE_PASSWORD_ENV):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.2",
            reason=RefusalReason.MISSING_SECRET,
            details={"missing_secret": _FIXTURE_PASSWORD_ENV},
        )
        return

    # Detection chain (registration → submit weak passwords → classify)
    # lands when the first fixture is provisioned with a canary account.
    return
