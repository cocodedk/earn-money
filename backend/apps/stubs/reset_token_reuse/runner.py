"""Stub 2.6 runner — reset-token-reuse.

Detects password-reset flows where a token remains valid after it
has been consumed once. Detection chain:

1. RoE gate (`allow_password_reset_probes`).
2. Mailbox + authorized canary account.
3. Discover the reset form (reuse stub 2.5's helper).
4. Request a reset → wait for the email → extract the token.
5. POST `/reset-password` with the token + a fresh password. Expect
   2xx (the first consumption legitimately succeeds).
6. POST `/reset-password` AGAIN with the SAME token + ANOTHER new
   password. If this ALSO returns 2xx, the target did not
   invalidate the token after first use → Finding(category=
   auth_reset_token_reuse, severity=HIGH, confidence=high).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.mailbox import (
    MailboxBackend, MailboxConfigError, extract_reset_token,
    load_mailbox_backend,
)
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.scope_check import enforce_scope
from apps.targets.models import ScanTarget

from ..predictable_reset_token.discovery import fetch_and_find_reset_form
from ..predictable_reset_token.submit import request_reset
from ..runners import guarded_runner
from .submit import complete_reset


_STUB_ID = "2.6"
_CATEGORY = "auth_reset_token_reuse"
_CONFIDENCE = "high"

# Codex P1 — the canary account's password gets RESET by this stub.
# The operator must supply known replacement values so they can log
# back in after the scan; using random values would silently lock
# them out of any real-world canary. The env vars are also the
# consent signal that the operator has accepted the password-
# mutation risk.
#
# Codex pass-3 P2 — the SECOND consumption uses a DIFFERENT
# operator-configured password so targets enforcing "new password
# must differ from current" don't suppress the load-bearing signal.
# Both values are operator-supplied (not derived) so any password
# policy on the target — max length, charset restrictions, ban-
# list — is the operator's to respect when they pick the values.
_REPLACEMENT_PASSWORD_ENV = "FIXTURE_RESET_REPLACEMENT_PASSWORD"
_REPLACEMENT_PASSWORD_2_ENV = "FIXTURE_RESET_REPLACEMENT_PASSWORD_2"


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
    replacement_password = os.environ.get(_REPLACEMENT_PASSWORD_ENV)
    replacement_password_2 = os.environ.get(_REPLACEMENT_PASSWORD_2_ENV)
    if not replacement_password:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.MISSING_SECRET,
            details={"missing_secret": _REPLACEMENT_PASSWORD_ENV,
                     "detail": "reset_replacement_password_required"},
        )
        return
    if not replacement_password_2:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.MISSING_SECRET,
            details={"missing_secret": _REPLACEMENT_PASSWORD_2_ENV,
                     "detail": "reset_replay_password_required"},
        )
        return
    if replacement_password == replacement_password_2:
        # Codex pass-4 P2: targets enforcing "new password must
        # differ from current" would reject the second POST purely
        # on policy, hiding a still-reusable token. Refuse before
        # any consumption fires.
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "reset_replay_password_must_differ"},
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
        enforce_scope(
            target, discovery.form.action_url, program,
            scan_run=scan_run, stub_id=_STUB_ID,
        )
    except OutOfScope:
        return

    token = _capture_token(
        form=discovery.form, canary=canary, mailbox=mailbox,
        program=program,
    )
    if token is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_reset_email_received"},
        )
        return

    # First consumption — should succeed on any normal target. The
    # second consumption uses a DIFFERENT operator-configured
    # password so targets enforcing "new password must differ from
    # current" don't suppress the load-bearing signal. Both values
    # are operator-supplied (not derived), so any password policy
    # on the target is the operator's to satisfy when picking them.
    acquire_for(program)
    first = complete_reset(
        base_url=target.base_url, token=token, password=replacement_password,
    )
    if first is None or not (200 <= first.status_code < 300):
        return  # Target rejected the first consumption — can't probe reuse.

    # Second consumption with SAME token — the load-bearing probe.
    acquire_for(program)
    second = complete_reset(
        base_url=target.base_url, token=token, password=replacement_password_2,
    )
    if second is None or not (200 <= second.status_code < 300):
        return  # Token invalidated on first use → target is OK.

    _emit_finding(
        scan_run=scan_run, target=target,
        action_url=discovery.form.action_url,
        first_status=first.status_code, second_status=second.status_code,
    )


def _load_mailbox_or_refuse(
    scan_run: ScanRun, target_run: ScanTargetRun,
) -> MailboxBackend | None:
    try:
        mailbox = load_mailbox_backend()
    except MailboxConfigError as exc:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mailbox_unconfigured", "error": str(exc)},
        )
        return None
    if mailbox is None:
        # FIXTURE_MAILBOX_BACKEND=none → target doesn't send email;
        # can't probe a reset-flow stub. Codex P2 — emit a refusal so
        # operators see why the stub didn't run.
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mailbox_required_for_reset"},
        )
        return None
    return mailbox


def _capture_token(
    *, form, canary: str, mailbox: MailboxBackend, program: Program,
) -> str | None:
    """One forgot-password POST, then poll the mailbox for the link."""
    acquire_for(program)
    since = datetime.now(timezone.utc)
    if not request_reset(form=form, identifier_value=canary):
        return None
    msg = mailbox.wait_for_message(canary, since=since, timeout_s=30.0)
    if msg is None:
        return None
    return extract_reset_token(msg)


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, action_url: str,
    first_status: int, second_status: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="Reset token remains valid after first consumption",
        category=_CATEGORY,
        severity=Severity.HIGH,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "action_url": action_url,
            "first_consumption_status": first_status,
            "second_consumption_status": second_status,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
