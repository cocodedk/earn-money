"""Stub 2.13 runner — MFA reset abuse.

Detects targets that allow MFA to be DISABLED on an account
without an MFA step-up (no current TOTP, no current password
re-prompt). The attack: hijack a session → disable MFA → run a
normal password reset → full account takeover.

Detection chain:
1. RoE gates: `allow_registration_probes` + `allow_active_login_
   probes` + `allow_mfa_probes`.
2. Register + login + enroll MFA on a synthetic account.
3. Confirm enrollment landed (`verify_mfa_enrolled`) — same
   pre-condition as 2.10. Without this, a non-MFA account would
   yield a high-confidence false positive.
4. POST `/mfa/disable` (candidate paths) with ONLY the ordinary
   session bearer — no step-up header, no current_password body.
5. Re-check `verify_mfa_enrolled`. If it now returns False, the
   target accepted the no-step-up disable → Finding(category=
   auth_mfa_reset_abuse, severity=HIGH, confidence=high).
   If it stays True (MFA still on), the target's response was
   non-sequitur — no Finding.

Reuses `enroll_mfa` and `verify_mfa_enrolled` from stub 2.10's
shared submit module so the auth scaffolding stays in one place.
"""
from __future__ import annotations

import secrets

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.identifiers import generate_invalid_identifier
from apps.stubs._shared.auth.login import login_via_api
from apps.stubs._shared.auth.register import register_via_api
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.targets.models import ScanTarget

from ..email_change_takeover.submit import bearer_token_from
from ..mfa_bypass.submit import enroll_mfa, verify_mfa_enrolled
from ..runners import guarded_runner
from .submit import disable_mfa


_STUB_ID = "2.13"
_CATEGORY = "auth_mfa_reset_abuse"
_CONFIDENCE = "high"


@guarded_runner(_STUB_ID)
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    target = target_run.target
    if not program.roe.allow_registration_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_registration_probes"},
        )
        return
    if not program.roe.allow_active_login_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_active_login_probes"},
        )
        return
    if not program.roe.allow_mfa_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_mfa_probes"},
        )
        return

    canary_email = generate_invalid_identifier("email")
    canary_password = f"scanner-mra-{secrets.token_hex(8)}"

    acquire_for(program)
    reg = register_via_api(
        base_url=target.base_url,
        email=canary_email, password=canary_password,
    )
    if reg is None or not (200 <= reg.status_code < 300):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "register_endpoint_unreachable_or_rejected"},
        )
        return

    acquire_for(program)
    login = login_via_api(
        base_url=target.base_url,
        email=canary_email, password=canary_password,
    )
    if login is None or not (200 <= login.status_code < 300):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "login_endpoint_unreachable_or_rejected"},
        )
        return

    token = bearer_token_from(login)
    if token is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "login_response_yielded_no_token"},
        )
        return

    acquire_for(program)
    enroll = enroll_mfa(base_url=target.base_url, bearer_token=token)
    if enroll is None or not (200 <= enroll.status_code < 300):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mfa_enroll_endpoint_unreachable_or_rejected"},
        )
        return

    acquire_for(program)
    pre_state = verify_mfa_enrolled(
        base_url=target.base_url, bearer_token=token,
    )
    if pre_state is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mfa_state_endpoint_unreachable"},
        )
        return
    if pre_state is False:
        # Target rejected the enrollment silently; without confirmed
        # MFA-on state we can't claim a reset abuse.
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mfa_enrollment_did_not_land"},
        )
        return

    acquire_for(program)
    disable = disable_mfa(base_url=target.base_url, bearer_token=token)
    if disable is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mfa_disable_endpoint_unreachable"},
        )
        return
    if not (200 <= disable.status_code < 300):
        return  # Target rejected the no-step-up disable → safe.

    acquire_for(program)
    post_state = verify_mfa_enrolled(
        base_url=target.base_url, bearer_token=token,
    )
    if post_state is None or post_state is True:
        # Endpoint returned 2xx but MFA state didn't actually change;
        # not a real bypass.
        return

    _emit_finding(
        scan_run=scan_run, target=target,
        disable_status=disable.status_code,
    )


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, disable_status: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="MFA can be disabled without re-authentication",
        category=_CATEGORY,
        severity=Severity.HIGH,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "disable_endpoint_status": disable_status,
            "synthetic_email_pattern": "scanner-*@example.invalid",
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
