"""Stub 2.10 runner — MFA bypass on a sensitive endpoint.

Detects targets where an MFA-enrolled account can still perform
sensitive actions with only an ordinary session token — no MFA
step-up challenge required. The canonical attack: a session that
hasn't completed MFA (or a refresh token used outside the MFA
flow) gets to call an endpoint that's supposed to be gated by
MFA, yielding a complete bypass.

MVP detection (single active probe after auth):
1. RoE gates: `allow_registration_probes` + `allow_active_login_
   probes` + `allow_mfa_probes` (the stub mutates the canary's
   MFA state, so all three opt-ins are required).
2. Register a scanner-owned synthetic account.
3. Log in via `login_via_api` to get a bearer token.
4. POST `/mfa/enroll` (candidate paths) with the token to flip
   `mfaEnabled=true` on the canary.
5. GET `/me` to confirm enrollment landed. The mfaEnabled flag
   gating the downstream signal must be true; otherwise the
   target didn't actually accept the enrollment and there's no
   bypass story to tell.
6. POST `/sensitive-action` (candidate paths) with ONLY the
   ordinary session bearer — no `X-MFA-Step-Up` or equivalent
   header. If 2xx → Finding(category=auth_mfa_bypass, severity=
   HIGH, confidence=high, status=candidate). If 401/403 → safe.

Reuses `register_via_api` / `login_via_api` / `bearer_token_from`
from the shared / 2.9 helpers so the auth scaffolding stays in
one place.
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
from ..runners import guarded_runner
from .submit import enroll_mfa, post_sensitive_action


_STUB_ID = "2.10"
_CATEGORY = "auth_mfa_bypass"
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
    canary_password = f"scanner-mfa-{secrets.token_hex(8)}"

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
    sensitive = post_sensitive_action(
        base_url=target.base_url, bearer_token=token,
    )
    if sensitive is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "sensitive_action_endpoint_unreachable"},
        )
        return
    if not (200 <= sensitive.status_code < 300):
        return  # Target refused without MFA step-up → safe.

    _emit_finding(
        scan_run=scan_run, target=target,
        sensitive_status=sensitive.status_code,
    )


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, sensitive_status: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="Sensitive endpoint accepts ordinary session despite MFA enrollment",
        category=_CATEGORY,
        severity=Severity.HIGH,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "sensitive_action_status": sensitive_status,
            "synthetic_email_pattern": "scanner-*@example.invalid",
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
