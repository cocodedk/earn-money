"""Stub 2.3 runner — missing-lockout.

Detects login flows that accept many consecutive failed
authentication attempts for the same account without lockout /
cooldown / rate-limit / CAPTCHA. Bounded per the spec: 5 failed
attempts, 750ms delay between each, scanner-owned account only.

Flow:
1. RoE gate (`allow_active_login_probes`).
2. Authorized test account required.
3. GET base URL → discover an HTML login form (password field).
4. Submit up to N (=5) failed attempts via the shared probe builder
   with a fresh synthetic wrong password each call.
5. After each response, `classify_abort_body` checks for lockout /
   WAF / CAPTCHA / rate-limit / MFA. The first abort signal → no
   Finding (the target enforces SOMETHING; the dashboard sees the
   refusal event, not a vulnerability claim).
6. If N attempts complete without any abort → Finding(
   category=auth_missing_lockout, severity=HIGH, confidence=medium,
   status=CANDIDATE) with `requires_manual_review=True` per the
   spec's "baseline known-good verification deferred" branch.
"""
from __future__ import annotations

import secrets
import time

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth._normalize_abort import classify_abort_body
from apps.stubs._shared.auth.forms import AuthForm, discover_forms
from apps.stubs._shared.auth.requests import build_probe_pair
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.scope_check import enforce_scope

from ..runners import guarded_runner
from ..username_enum.fetcher import fetch_for_discovery
from ..username_enum.submit import submit_probe


_STUB_ID = "2.3"
_CATEGORY = "auth_missing_lockout"
_CONFIDENCE = "medium"
_MAX_FAILED_ATTEMPTS = 5
_DELAY_BETWEEN_ATTEMPTS_S = 0.75


@guarded_runner(_STUB_ID)
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    target = target_run.target
    if not program.roe.allow_active_login_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_active_login_probes"},
        )
        return
    if not program.roe.authorized_test_accounts:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_authorized_test_accounts"},
        )
        return

    canary = program.roe.authorized_test_accounts[0]
    outcome = fetch_for_discovery(target.base_url)
    if not outcome.ok:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"error": outcome.error},
        )
        return
    try:
        enforce_scope(
            target, outcome.final_url, program,
            scan_run=scan_run, stub_id=_STUB_ID,
        )
    except OutOfScope:
        return
    forms = discover_forms(
        outcome.body, outcome.final_url,
        response_content_type=outcome.content_type,
    )
    login_form = _pick_login_form(forms)
    if login_form is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_login_form_found"},
        )
        return

    attempts = _run_attempt_loop(canary=canary, form=login_form)
    if attempts is None:
        return
    _emit_finding(
        scan_run=scan_run, target=target, form=login_form,
        attempts=attempts,
    )


def _pick_login_form(forms: list[AuthForm]) -> AuthForm | None:
    """Login forms without a password field can't test lockout."""
    for f in forms:
        if f.flow_hint == "login" and f.password_field is not None:
            return f
    return None


def _run_attempt_loop(*, canary: str, form: AuthForm) -> int | None:
    """Submit up to N failed-login attempts. Returns the count
    actually submitted on a clean sweep, or None when the target
    blocked us (lockout / rate-limit / CAPTCHA / WAF / MFA / transport
    failure) — both mean no finding."""
    for attempt in range(_MAX_FAILED_ATTEMPTS):
        if attempt > 0:
            time.sleep(_DELAY_BETWEEN_ATTEMPTS_S)
        wrong = f"scanner-wrong-{secrets.token_hex(4)}"
        pair = build_probe_pair(
            form=form, invalid_identifier=canary,
            valid_identifier=None, bogus_password=wrong,
        )
        resp = submit_probe(pair.invalid_request)
        if resp is None:
            return None
        if classify_abort_body(resp.text or "") is not None:
            return None
    return _MAX_FAILED_ATTEMPTS


def _emit_finding(
    *, scan_run, target, form: AuthForm, attempts: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=f"No lockout after {attempts} failed login attempts",
        category=_CATEGORY,
        severity=Severity.HIGH,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "failed_attempts": attempts,
            "action_url": form.action_url,
            "identifier_field": form.identifier_field,
            "requires_manual_review": True,
        },
    )
    Event.log(
        type=EventType.AUTH_FINDING_CANDIDATE,
        scan_run=scan_run, target=target, subject=finding,
        data={"finding_id": str(finding.id), "stub": _STUB_ID},
    )
