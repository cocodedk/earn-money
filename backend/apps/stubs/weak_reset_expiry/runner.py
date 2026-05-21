"""Stub 2.7 runner — weak-reset-expiry.

Detects password-reset flows whose emails carry tokens with no
declared expiry window. Operators rely on the time bound mentioned
in the message ("expires in 30 minutes") to set user expectations
and to provide audit-time evidence of intended expiry; its absence
is a signal the target may also lack server-side enforcement.

MVP scope: passive scan of the captured email body. Active-reuse-
after-delay confirmation is a follow-up (it needs either a fast-
forward clock fixture or a long-running probe budget the local
fixture can't yet provide).

Flow:
1. RoE gate (`allow_password_reset_probes`).
2. Mailbox + authorized canary account.
3. Discover the reset form (reuse stub 2.5's helper).
4. enforce_scope on the form action_url.
5. request_reset → wait for the email.
6. Scan the email body for any expiry-marker phrase
   (`_EXPIRY_MARKERS`, case-insensitive). If ANY marker is present,
   the target announces expiry → no Finding. If none → Finding(
   category=auth_weak_reset_expiry, severity=MEDIUM, confidence=
   low, status=candidate, requires_manual_review=True).
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.mailbox import (
    InboundMessage, MailboxBackend, MailboxConfigError,
    load_mailbox_backend,
)
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.scope_check import enforce_scope
from apps.targets.models import ScanTarget

from ..predictable_reset_token.discovery import fetch_and_find_reset_form
from ..predictable_reset_token.submit import request_reset
from ..runners import guarded_runner


_STUB_ID = "2.7"
_CATEGORY = "auth_weak_reset_expiry"
_CONFIDENCE = "low"

# Phrases that indicate the email announces an expiry window. ANY
# match (case-insensitive substring) means the target IS declaring
# an expiry → no finding. Conservative list — false-positive on
# "the link will not expire" would only suppress a low-confidence
# finding, so the bias toward suppression is intentional.
_EXPIRY_MARKERS: tuple[str, ...] = (
    "expire",
    "valid for",
    "valid until",
    "within the next",
    "good for",
    "minutes",
    "hours",
)


@guarded_runner(_STUB_ID)
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    target = target_run.target
    if not program.roe.allow_password_reset_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_password_reset_probes"},
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

    mailbox = _load_mailbox_or_refuse(scan_run, target_run)
    if mailbox is None:
        return

    discovery = fetch_and_find_reset_form(target.base_url)
    if discovery.error is not None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"error": discovery.error},
        )
        return
    if discovery.form is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_reset_form_found"},
        )
        return
    try:
        enforce_scope(
            target, discovery.final_url, program,
            scan_run=scan_run, stub_id=_STUB_ID,
        )
    except OutOfScope:
        return

    message = _capture_message(
        form=discovery.form, canary=canary, mailbox=mailbox,
        program=program,
    )
    if message is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_reset_email_received"},
        )
        return

    if _announces_expiry(message):
        return
    _emit_finding(
        scan_run=scan_run, target=target,
        action_url=discovery.form.action_url,
        body_snippet=(message.body_text or message.body_html or "")[:200],
    )


def _load_mailbox_or_refuse(
    scan_run: ScanRun, target_run: ScanTargetRun,
) -> MailboxBackend | None:
    try:
        return load_mailbox_backend()
    except MailboxConfigError as exc:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mailbox_unconfigured", "error": str(exc)},
        )
        return None


def _capture_message(
    *, form, canary: str, mailbox: MailboxBackend, program: Program,
) -> InboundMessage | None:
    acquire_for(program)
    since = datetime.now(timezone.utc)
    if not request_reset(form=form, identifier_value=canary):
        return None
    return mailbox.wait_for_message(canary, since=since, timeout_s=30.0)


def _announces_expiry(message: InboundMessage) -> bool:
    """True if either body part contains any expiry-marker phrase."""
    combined = ((message.body_text or "") + " " +
                (message.body_html or "")).lower()
    return any(marker in combined for marker in _EXPIRY_MARKERS)


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, action_url: str,
    body_snippet: str,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="Reset email announces no expiry window",
        category=_CATEGORY,
        severity=Severity.MEDIUM,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "action_url": action_url,
            "body_snippet": body_snippet,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
