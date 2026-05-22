"""Stub 2.21 runner — invitation-abuse."""
from __future__ import annotations

import os

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.targets.models import ScanTarget

from ..runners import guarded_runner
from .classify import (
    classify_invite_surface,
    classify_preview_exposure,
    classify_wrong_recipient,
)


_FIXTURE_SECRET_ENV = "FIXTURE_INVITATION_TOKEN"
_FIXTURE_URL_ENV = "FIXTURE_INVITE_LAB_URL"
_STUB_ID = "2.21"


@guarded_runner(_STUB_ID)
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    if not program.roe.allow_registration_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_registration_probes"},
        )
        return

    if not program.roe.authorized_test_accounts:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_authorized_test_accounts"},
        )
        return

    invite_token = os.environ.get(_FIXTURE_SECRET_ENV)
    if not invite_token:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.MISSING_SECRET,
            details={"missing_secret": _FIXTURE_SECRET_ENV},
        )
        return

    target = target_run.target
    base = os.environ.get(_FIXTURE_URL_ENV, target.base_url).rstrip("/")
    accounts = program.roe.authorized_test_accounts

    with httpx.Client(follow_redirects=False, timeout=10) as http:
        login = http.post(
            base + "/login",
            json={"username": accounts[0], "password": "pass-inviter"},
        )
    if login.status_code != 200:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "fixture_login_failed"},
        )
        return
    session_headers = {"X-Session-Token": login.json().get("token", "")}

    # Probe 1: surface discovery (authenticated)
    acquire_for(program)
    surface_req = httpx.Request("GET", base + "/fixture/invitations", headers=session_headers)
    surface_resp = submit_probe(surface_req)
    if surface_resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "target_unreachable:/fixture/invitations"},
        )
        return
    classify_invite_surface(surface_resp, base + "/fixture/invitations")

    # Probe 2: preview exposure (unauthenticated GET to invite token URL)
    acquire_for(program)
    preview_url = f"{base}/fixture/invitations/{invite_token}"
    preview_req = httpx.Request("GET", preview_url)
    preview_resp = submit_probe(preview_req)
    if preview_resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": f"target_unreachable:/fixture/invitations/{invite_token}"},
        )
        return

    preview_flaw = classify_preview_exposure(preview_resp, preview_url)
    if preview_flaw is not None:
        _emit_finding(scan_run=scan_run, target=target, flaw=preview_flaw)
        return

    # Probe 3: wrong-recipient acceptance (unrelated session tries to accept)
    accept_url = f"{base}/fixture/invitations/{invite_token}/accept"
    acquire_for(program)
    accept_req = httpx.Request("POST", accept_url, headers=session_headers)
    accept_resp = submit_probe(accept_req)
    if accept_resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": f"target_unreachable:{accept_url}"},
        )
        return

    wrong_flaw = classify_wrong_recipient(accept_resp, accept_url)
    if wrong_flaw is not None:
        _emit_finding(scan_run=scan_run, target=target, flaw=wrong_flaw)


def _emit_finding(
    *, scan_run: "ScanRun", target: "ScanTarget", flaw: object,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=f"Invitation abuse: {flaw.kind.value}",  # type: ignore[attr-defined]
        category="invitation_abuse",
        severity=Severity.MEDIUM,
        confidence=flaw.confidence,  # type: ignore[attr-defined]
        status=FindingStatus.CANDIDATE,
        data={
            "kind": flaw.kind.value,  # type: ignore[attr-defined]
            "endpoint": flaw.endpoint_url,  # type: ignore[attr-defined]
            "method": flaw.http_method,  # type: ignore[attr-defined]
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
