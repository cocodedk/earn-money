"""Stub 2.18 runner — login-csrf (HTML form, GET-only).

Detects login HTML forms that lack a CSRF token field. MVP scope:
form-based logins only. OAuth/OIDC state-parameter inspection is a
follow-up — that branch requires redirect-chain inspection and is
GET-only too but materially different.

Flow:
1. GET base URL via `fetch_for_discovery` (no credentials, no
   mutating method — fully passive).
2. Enforce scope on the final URL.
3. Discover forms; pick the first login form (`flow_hint=login` +
   password field).
4. Check `form.hidden_fields` for any input name matching the
   `_CSRF_FIELD_NAMES` set. ANY match → no finding (form is
   protected). NO match → Finding(category=auth_login_csrf,
   severity=MEDIUM, confidence=medium, status=CANDIDATE,
   indicator=missing_form_csrf_token, requires_manual_review=True).

No RoE gate — this stub never POSTs, never mutates state, never
sends credentials. `scope_check.enforce_scope` is the only gate.
"""
from __future__ import annotations

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.discovery import fetch_for_discovery
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.forms import (
    AuthForm, discover_forms, pick_login_form,
)
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.scope_check import enforce_scope
from apps.targets.models import ScanTarget

from ..runners import guarded_runner


_STUB_ID = "2.18"
_CATEGORY = "auth_login_csrf"
_CONFIDENCE = "medium"
_INDICATOR = "missing_form_csrf_token"

# Hidden-field input names that signal anti-CSRF protection per
# spec §"Token detection". Match is case-insensitive against the
# hidden-field name. ANY match means the form is protected → no
# finding. `user_token` is the DVWA-specific anti-CSRF field name;
# the spec invites "input names such as" — adding canonical
# server-rendered variants here keeps every login stub aligned.
_CSRF_FIELD_NAMES: frozenset[str] = frozenset({
    "csrf",
    "_csrf",
    "csrf_token",
    "csrftoken",
    "authenticity_token",
    "request_verification_token",
    "__requestverificationtoken",
    "user_token",
})


@guarded_runner(_STUB_ID)
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    target = target_run.target
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

    if _has_csrf_field(login_form):
        return
    _emit_finding(
        scan_run=scan_run, target=target, form=login_form,
    )


def _has_csrf_field(form: AuthForm) -> bool:
    """True if any hidden-field name (case-insensitive) is in the
    canonical anti-CSRF token set."""
    return any(
        name.lower() in _CSRF_FIELD_NAMES
        for name in (form.hidden_fields or {})
    )


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, form: AuthForm,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="Login form has no anti-CSRF token field",
        category=_CATEGORY,
        severity=Severity.MEDIUM,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "indicator": _INDICATOR,
            "action_url": form.action_url,
            "identifier_field": form.identifier_field,
            "hidden_field_names": sorted(form.hidden_fields or {}),
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
