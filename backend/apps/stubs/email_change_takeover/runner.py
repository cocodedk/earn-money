"""Stub 2.9 runner — account-takeover-via-email-change.

Detects accounts whose email can be swapped out by an authenticated
session WITHOUT re-prompting for the current password. An attacker
who hijacks a session (XSS, replay, etc.) can flip the email to one
they control, then run a normal password-reset → full takeover.

MVP detection (cheap, single active request after auth):
1. RoE gate (`allow_registration_probes` + a fresh
   `allow_active_login_probes` requirement).
2. Register a scanner-owned synthetic account on the target
   (`register_via_api` from `_shared/auth/register`).
3. Log in via `login_via_api` to obtain a session token.
4. POST `/change-email` (candidate paths) with the session token
   and ONLY a `new_email` body — NO `current_password` field. The
   probe deliberately tests whether the target requires re-auth.
5. If the response is 2xx → Finding(category=auth_email_change_
   takeover, severity=HIGH, confidence=high, status=candidate). If
   it's 4xx (re-auth required, validation rejected) → no Finding.

No real customer accounts are touched: the synthetic identifier
lives on `example.invalid` per RFC 6761. The replacement email
also lives on `example.invalid`.
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

from ..runners import guarded_runner
from .submit import bearer_token_from, change_email_unauthed_password


_STUB_ID = "2.9"
_CATEGORY = "auth_email_change_takeover"
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

    canary_email = generate_invalid_identifier("email")
    canary_password = f"scanner-ec-{secrets.token_hex(8)}"

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

    new_email = generate_invalid_identifier("email")
    acquire_for(program)
    change = change_email_unauthed_password(
        base_url=target.base_url, bearer_token=token, new_email=new_email,
    )
    if change is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "change_email_endpoint_unreachable"},
        )
        return
    if not (200 <= change.status_code < 300):
        return  # Target rejected the no-password change → safe.

    _emit_finding(
        scan_run=scan_run, target=target,
        change_status=change.status_code,
    )


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, change_status: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="Email can be changed without re-authentication",
        category=_CATEGORY,
        severity=Severity.HIGH,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "change_email_status": change_status,
            "synthetic_email_pattern": "scanner-*@example.invalid",
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
