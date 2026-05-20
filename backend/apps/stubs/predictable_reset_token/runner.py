"""Stub 2.5 runner — predictable reset token.

Flow (per spec 05-predictable-reset-tokens.md):
1. RoE gate (`allow_password_reset_probes`).
2. Authorized test account + mailbox backend.
3. Discover the reset form on the target.
4. Loop N times: POST the reset request → wait for email →
   extract token.
5. `analyse_tokens()` classifies the sample.
6. Emit Finding(category=`auth_predictable_reset_token`) when
   the analysis returns verdict=predictable.
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.forms import AuthForm
from apps.stubs._shared.auth.mailbox import (
    MailboxBackend, MailboxConfigError, extract_reset_token,
    load_mailbox_backend,
)
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.auth.token_analysis import (
    TokenAnalysis, analyse_tokens,
)
from apps.stubs._shared.scope_check import enforce_scope

from ..runners import guarded_runner
from .discovery import fetch_and_find_reset_form
from .submit import request_reset


_TOKEN_SAMPLE_SIZE = 8
_PER_PROBE_TIMEOUT_S = 60.0

_SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
}


@guarded_runner("2.5")
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    target = target_run.target
    if not program.roe.allow_active_login_probes and \
            not program.roe.allow_password_reset_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.5",
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_password_reset_probes"},
        )
        return
    if not program.roe.allow_password_reset_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.5",
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_password_reset_probes"},
        )
        return
    if not program.roe.authorized_test_accounts:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.5",
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_authorized_test_accounts"},
        )
        return
    canary = program.roe.authorized_test_accounts[0]

    mailbox = _load_mailbox_or_refuse(scan_run, target_run)
    if mailbox is None:
        return

    discovery = fetch_and_find_reset_form(target.base_url)
    if discovery.error is not None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.5",
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"error": discovery.error},
        )
        return
    if discovery.form is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.5",
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_reset_form_found"},
        )
        return

    try:
        enforce_scope(
            target, discovery.final_url, program,
            scan_run=scan_run, stub_id="2.5",
        )
    except OutOfScope:
        return

    tokens = _collect_tokens(
        form=discovery.form, canary=canary, mailbox=mailbox,
    )
    analysis = analyse_tokens(tokens)
    if analysis.verdict == "predictable":
        _emit_finding(
            scan_run=scan_run, target=target, form=discovery.form,
            analysis=analysis,
        )
    elif analysis.verdict == "inconclusive":
        _emit_stale(
            scan_run=scan_run, target=target, tokens_collected=len(tokens),
        )


def _load_mailbox_or_refuse(
    scan_run: ScanRun, target_run: ScanTargetRun,
) -> MailboxBackend | None:
    try:
        mailbox = load_mailbox_backend()
    except MailboxConfigError as exc:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.5",
            reason=RefusalReason.MISSING_SECRET,
            details={"missing_secret": "FIXTURE_MAILBOX_*",
                     "error": str(exc)},
        )
        return None
    if mailbox is None:
        # BACKEND=none → target doesn't email; can't test reset flow.
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.5",
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mailbox_required_for_reset"},
        )
        return None
    return mailbox


def _collect_tokens(
    *, form: AuthForm, canary: str, mailbox: MailboxBackend,
) -> list[str]:
    tokens: list[str] = []
    for _ in range(_TOKEN_SAMPLE_SIZE):
        since = datetime.now(timezone.utc)
        if not request_reset(form=form, identifier_value=canary):
            break
        msg = mailbox.wait_for_message(
            canary, since=since, timeout_s=_PER_PROBE_TIMEOUT_S,
        )
        if msg is None:
            break
        token = extract_reset_token(msg)
        if token is None:
            break
        tokens.append(token)
    return tokens


def _emit_finding(
    *, scan_run: ScanRun, target, form: AuthForm,
    analysis: TokenAnalysis,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.5",
        title=f"Predictable reset tokens — signal={analysis.signal}",
        category="auth_predictable_reset_token",
        severity=_SEVERITY_MAP[analysis.severity],
        confidence=(
            "high" if analysis.signal == "sequential_integer" else "medium"
        ),
        status=FindingStatus.CANDIDATE,
        data={
            "signal": analysis.signal,
            "sample_size": analysis.sample_size,
            "entropy_bits_per_char": round(analysis.entropy_bits_per_char, 3),
            "shared_prefix_len": analysis.shared_prefix_len,
            "action_url": form.action_url,
        },
    )
    Event.log(
        type=EventType.AUTH_FINDING_CANDIDATE,
        scan_run=scan_run, target=target, subject=finding,
        data={"finding_id": str(finding.id), "stub": "2.5"},
    )


def _emit_stale(
    *, scan_run: ScanRun, target, tokens_collected: int,
) -> None:
    Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.5",
        title="Reset-token analysis inconclusive — sample too small",
        category="auth_predictable_reset_token",
        severity=Severity.INFO, confidence="low",
        status=FindingStatus.STALE,
        data={"sample_size": tokens_collected,
              "detail": "could_not_collect_enough_tokens"},
    )
