"""Stub 2.4 runner — weak-rate-limiting.

Detects login endpoints that accept many consecutive failed
authentication attempts without ANY throttle / rate-limit / temporary-
block / CAPTCHA / lockout signal. Bounded per the spec: 6 attempts
(policy_max_failures_without_throttle + 1), 250ms apart, scanner-
generated synthetic credentials reused across all attempts.

Flow:
1. RoE gate (`allow_active_login_probes`).
2. GET base URL → discover an HTML login form (password field).
3. Generate ONE synthetic invalid identifier + ONE synthetic bogus
   password — reused for every attempt so the probe stays focused
   on request throttling, NOT password guessing.
4. Submit up to N (=6) attempts via the shared probe builder.
5. After each response, `is_throttled` checks status 429,
   Retry-After / RateLimit-* / X-RateLimit-* headers, and a broader
   body-marker set (composed with `classify_abort_body`). First
   throttle signal → no Finding (the target enforces SOMETHING).
6. If N attempts complete without any throttle → Finding(
   category=auth_weak_rate_limiting, severity=MEDIUM, confidence=
   medium, status=CANDIDATE, requires_manual_review=True).

No `authorized_test_accounts` gate — spec §2 prefers a scanner-
generated nonexistent identity by default, so the stub doesn't
require a canary account.
"""
from __future__ import annotations

import secrets
import time

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.discovery import fetch_for_discovery
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.forms import (
    AuthForm, discover_forms, pick_login_form,
)
from apps.stubs._shared.auth.identifiers import generate_invalid_identifier
from apps.stubs._shared.auth.requests import build_probe_pair, submit_probe
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.auth.throttle import is_throttled
from apps.stubs._shared.scope_check import enforce_scope
from apps.targets.models import ScanTarget

from ..runners import guarded_runner


_STUB_ID = "2.4"
_CATEGORY = "auth_weak_rate_limiting"
_CONFIDENCE = "medium"
_MAX_ATTEMPTS = 6
_DELAY_BETWEEN_ATTEMPTS_S = 0.25


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
    login_form = pick_login_form(forms)
    if login_form is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_login_form_found"},
        )
        return

    attempts = _run_attempt_loop(form=login_form)
    if attempts is None:
        return
    _emit_finding(
        scan_run=scan_run, target=target, form=login_form,
        attempts=attempts,
    )


def _run_attempt_loop(*, form: AuthForm) -> int | None:
    """Submit up to N failed-login attempts with ONE synthetic
    invalid identifier reused across all attempts. Returns the count
    submitted on a clean sweep, or None when the target throttled us
    / transport failed — both mean no finding."""
    synthetic_id = generate_invalid_identifier("email")
    bogus_pw = f"scanner-rl-{secrets.token_hex(8)}"
    for attempt in range(_MAX_ATTEMPTS):
        if attempt > 0:
            time.sleep(_DELAY_BETWEEN_ATTEMPTS_S)
        pair = build_probe_pair(
            form=form, invalid_identifier=synthetic_id,
            valid_identifier=None, bogus_password=bogus_pw,
        )
        resp = submit_probe(pair.invalid_request)
        if resp is None:
            return None
        if is_throttled(resp):
            return None
    return _MAX_ATTEMPTS


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, form: AuthForm, attempts: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=f"No rate-limit / throttle after {attempts} failed login attempts",
        category=_CATEGORY,
        severity=Severity.MEDIUM,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "attempts_sent": attempts,
            "action_url": form.action_url,
            "identifier_field": form.identifier_field,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
