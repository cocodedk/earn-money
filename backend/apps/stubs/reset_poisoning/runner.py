"""Stub 2.8 runner — reset-poisoning.

Detects password-reset flows that reflect caller-controlled
`Host:` / `X-Forwarded-Host:` headers into the reset link sent to
the user. An attacker who can fake the header can redirect the
victim's token to a domain they control.

Flow:
1. RoE gate (`allow_password_reset_probes`).
2. Mailbox + authorized canary account.
3. Discover the reset form (reuse stub 2.5's helper).
4. enforce_scope on the form action_url.
5. Send the forgot-password POST with `X-Forwarded-Host:
   <scanner-controlled-host>`. Wait for the email.
6. Parse the email body for the first URL; check whether its host
   matches the injected sentinel.
   * Host == sentinel → target reflected the header → Finding(
     category=auth_reset_poisoning, severity=HIGH, confidence=high,
     status=candidate).
   * Host != sentinel → target uses a hard-coded base URL → safe.

The injected host (`SCANNER_POISON_HOST`) lives on the
`example.invalid` TLD per RFC 6761 — guaranteed never to resolve
or land on a real user's machine if the email leaks.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.forms import AuthForm
from apps.stubs._shared.auth.mailbox import (
    MailboxBackend, MailboxConfigError, extract_link,
    load_mailbox_backend,
)
from apps.stubs._shared.auth.requests import SCANNER_USER_AGENT
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.scope_check import enforce_scope
from apps.targets.models import ScanTarget

from ..predictable_reset_token.discovery import fetch_and_find_reset_form
from ..runners import guarded_runner
from .submit import request_reset_with_host_header


_STUB_ID = "2.8"
_CATEGORY = "auth_reset_poisoning"
_CONFIDENCE = "high"
SCANNER_POISON_HOST = "poison-canary.example.invalid"


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
        enforce_scope(
            target, discovery.form.action_url, program,
            scan_run=scan_run, stub_id=_STUB_ID,
        )
    except OutOfScope:
        return

    link = _capture_link(
        form=discovery.form, canary=canary, mailbox=mailbox,
        program=program,
    )
    if link is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_reset_email_received"},
        )
        return

    link_host = urlsplit(link).hostname or ""
    if link_host.lower() != SCANNER_POISON_HOST:
        return  # Target ignores the header → not poisonable.
    _emit_finding(
        scan_run=scan_run, target=target,
        action_url=discovery.form.action_url, poisoned_link=link,
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
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mailbox_required_for_reset"},
        )
        return None
    return mailbox


def _capture_link(
    *, form: AuthForm, canary: str, mailbox: MailboxBackend, program: Program,
) -> str | None:
    """Fire the poisoning probe, wait for the email, extract the
    first reset link present (anywhere in the body)."""
    acquire_for(program)
    since = datetime.now(timezone.utc)
    if not request_reset_with_host_header(
        form=form, identifier_value=canary,
        x_forwarded_host=SCANNER_POISON_HOST,
        user_agent=SCANNER_USER_AGENT,
    ):
        return None
    msg = mailbox.wait_for_message(canary, since=since, timeout_s=30.0)
    if msg is None:
        return None
    # Prefer the canonical reset-bearing URL. Fall back to the first
    # URL in either body if "reset" doesn't appear (some targets
    # build the path differently).
    link = extract_link(msg, url_substring="reset")
    if link is not None:
        return link
    return _first_url(msg.body_text) or _first_url(msg.body_html)


_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _first_url(body: str) -> str | None:
    match = _URL_RE.search(body or "")
    return match.group(0) if match else None


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget, action_url: str,
    poisoned_link: str,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="Reset email reflects caller-controlled host header",
        category=_CATEGORY,
        severity=Severity.HIGH,
        confidence=_CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "action_url": action_url,
            "injected_host": SCANNER_POISON_HOST,
            "poisoned_link_host": urlsplit(poisoned_link).hostname,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
