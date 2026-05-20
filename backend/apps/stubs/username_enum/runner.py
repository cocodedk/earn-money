"""Stub 2.1 runner — username enumeration.

Phase 2 canary. Demonstrates the full active-auth-probe pattern that
remaining Phase 2 stubs follow:

1. `@guarded_runner("2.1")` handles scope + RECON_ENABLED + FROZEN
   + rate-limit at the Phase 1 layer. Declaring a `program=`
   keyword on `run()` opts in to receiving the resolved Program.
2. RoE knob check (`allow_active_login_probes`).
3. Discovery GET → auth-form parse → cross-origin scope re-check.
4. Per-form: build ProbePair → submit invalid + (optional) valid →
   normalize + diff → emit Finding when differentiators present.
"""
from __future__ import annotations

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.forms import AuthForm, discover_forms
from apps.stubs._shared.auth.identifiers import generate_invalid_identifier
from apps.stubs._shared.auth.normalize import (
    NormalizedResponse, classify_abort, diff, normalize,
)
from apps.stubs._shared.auth.requests import ProbePair, build_probe_pair
from apps.stubs._shared.auth.safety import (
    ProbeBudget, ProbeState, RefusalReason, check_can_probe, record_refusal,
)
from apps.stubs._shared.scope_check import enforce_scope

from ..runners import guarded_runner
from .fetcher import fetch_for_discovery
from .submit import submit_probe


_BOGUS_PASSWORD = "scanner-bogus-passphrase"
_BUDGET = ProbeBudget(
    stub_id="2.1", max_forms=2, max_submits=4,
    allow_repeat_confirmation=True,
)


@guarded_runner("2.1")
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    if not program.roe.allow_active_login_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.1",
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_active_login_probes"},
        )
        return

    target = target_run.target
    outcome = fetch_for_discovery(target.base_url)
    if not outcome.ok:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.1",
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"error": outcome.error},
        )
        return

    try:
        enforce_scope(
            target, outcome.final_url, program,
            scan_run=scan_run, stub_id="2.1",
        )
    except OutOfScope:
        return

    forms = discover_forms(
        outcome.body, outcome.final_url,
        response_content_type=outcome.content_type,
    )
    if not forms:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.1",
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_auth_form_found"},
        )
        return

    state = ProbeState()
    valid_identifier = _pick_valid_identifier(program)
    for form in forms:
        if not state.can_record_form(_BUDGET):
            break
        state.record_form()
        _probe_one_form(
            scan_run=scan_run, target_run=target_run, form=form,
            valid_identifier=valid_identifier, state=state,
        )


def _pick_valid_identifier(program: Program) -> str | None:
    """First authorized test account, or None if the roe.md lists
    none. Spec 2.1 §2.4 — comparison oracle is fixture-provided."""
    if program.roe.authorized_test_accounts:
        return program.roe.authorized_test_accounts[0]
    return None


def _probe_one_form(
    *,
    scan_run: ScanRun,
    target_run: ScanTargetRun,
    form: AuthForm,
    valid_identifier: str | None,
    state: ProbeState,
) -> None:
    refusal = check_can_probe(form, _BUDGET, state)
    if refusal is not None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.1",
            reason=refusal, details={"action_url": form.action_url},
        )
        return

    pair = build_probe_pair(
        form=form,
        invalid_identifier=generate_invalid_identifier(
            "email" if "email" in (form.identifier_field or "") else "username",
        ),
        valid_identifier=valid_identifier,
        bogus_password=_BOGUS_PASSWORD,
    )

    invalid_norm = _send_and_normalize(pair.invalid_request)
    state.record_submit()
    if invalid_norm is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.1",
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"action_url": form.action_url, "probe": "invalid"},
        )
        return
    if classify_abort(invalid_norm) is not None:
        return  # abort signal — no Finding promotion

    valid_norm: NormalizedResponse | None = None
    if pair.valid_request is not None:
        valid_norm = _send_and_normalize(pair.valid_request)
        state.record_submit()
        if valid_norm is None or classify_abort(valid_norm) is not None:
            valid_norm = None  # treat as invalid-only

    _maybe_emit_finding(
        scan_run=scan_run, target_run=target_run, form=form,
        invalid_norm=invalid_norm, valid_norm=valid_norm,
    )


def _send_and_normalize(request) -> NormalizedResponse | None:
    response = submit_probe(request)
    if response is None:
        return None
    return normalize(response)


def _maybe_emit_finding(
    *,
    scan_run: ScanRun,
    target_run: ScanTargetRun,
    form: AuthForm,
    invalid_norm: NormalizedResponse,
    valid_norm: NormalizedResponse | None,
) -> None:
    if valid_norm is None:
        if "not found" in invalid_norm.body_snippet.lower():
            _emit(
                scan_run=scan_run, target=target_run.target, form=form,
                differentiators_count=1, confidence="low",
                valid_identifier_used=False,
            )
        return

    differentiators = diff(invalid_norm, valid_norm)
    if not differentiators:
        return
    confidence = "high" if len(differentiators) >= 2 else "medium"
    _emit(
        scan_run=scan_run, target=target_run.target, form=form,
        differentiators_count=len(differentiators), confidence=confidence,
        valid_identifier_used=True,
    )


def _emit(
    *,
    scan_run: ScanRun, target, form: AuthForm,
    differentiators_count: int, confidence: str,
    valid_identifier_used: bool,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target,
        stub_slug="2.1",
        title=f"Username enumeration on {form.action_url}",
        category="auth_username_enum",
        severity=Severity.LOW,
        confidence=confidence,
        status=FindingStatus.CANDIDATE,
        data={
            "action_url": form.action_url,
            "flow_hint": form.flow_hint,
            "identifier_field": form.identifier_field,
            "differentiators_count": differentiators_count,
            "valid_identifier_used": valid_identifier_used,
        },
    )
    Event.log(
        type=EventType.AUTH_FINDING_CANDIDATE,
        scan_run=scan_run, target=target, subject=finding,
        data={"finding_id": str(finding.id), "stub": "2.1"},
    )
