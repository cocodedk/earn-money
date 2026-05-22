"""Stub 2.11 runner — missing-mfa-on-sensitive-flows.

Detects targets that expose sensitive actions without any MFA
challenge (no enrollment requirement, no step-up). The 2.10
sibling looks for bypass on an MFA-enrolled account; this stub
looks for absence — the endpoint accepts an ordinary session
token without ever asking for MFA.

Detection chain (simpler than 2.10 — no enrollment step):
1. RoE gates: `allow_registration_probes` + `allow_active_login_
   probes`. No `allow_mfa_probes` requirement — the stub never
   mutates MFA state.
2. Register a scanner-owned synthetic account.
3. Log in to get a bearer token.
4. POST `/sensitive-action` (candidate paths) with ONLY the
   ordinary session bearer — without enrolling MFA first.
5. If 2xx → Finding(category=auth_missing_mfa_on_sensitive_flow,
   severity=MEDIUM, confidence=low, status=candidate). Confidence
   is `low` (not `high` like 2.10) because the target may
   legitimately not require MFA on this endpoint; the operator
   reviews each candidate.
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
from ..mfa_bypass.submit import post_sensitive_action
from ..runners import guarded_runner


_STUB_ID = "2.11"
# Category matches the Phase 2 contract — the dashboard keys
# filters / aggregation off this exact string (codex P2.2).
_CATEGORY = "auth_mfa_missing_sensitive_flow"
_CONFIDENCE = "low"


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
    # 2.11 is part of the MFA probe family — codex P1.1 caught that
    # the previous version ran sensitive-action probes against
    # programs whose RoE explicitly disabled MFA testing.
    if not program.roe.allow_mfa_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_mfa_probes"},
        )
        return

    canary_email = generate_invalid_identifier("email")
    canary_password = f"scanner-mmfa-{secrets.token_hex(8)}"

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
        return  # Target requires MFA on the endpoint → safe.

    _emit_finding(
        scan_run=scan_run, target=target,
        sensitive_status=sensitive.status_code,
    )


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, sensitive_status: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="Sensitive endpoint accepts ordinary session without MFA prompt",
        category=_CATEGORY,
        severity=Severity.MEDIUM,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "sensitive_action_status": sensitive_status,
            "synthetic_email_pattern": "scanner-*@example.invalid",
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
