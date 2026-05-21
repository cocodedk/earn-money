"""Stub 2.17 runner — oauth-account-linking."""
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
from .classify import classify_link_flaw


_FIXTURE_SECRET_ENV = "FIXTURE_OAUTH_CLIENT_SECRET"
_STUB_ID = "2.17"

_CANDIDATE_PROBES = [
    ("GET", "/auth/link/start", None, False),
    ("GET", "/settings/connections/link/mock", None, False),
    ("POST", "/auth/link/callback", {"code": "code-fixture"}, True),
    ("GET", "/auth/link/callback-client-id?provider_user_id=scanner-controlled", None, False),
    ("GET", "/settings/connections", None, False),
]


@guarded_runner(_STUB_ID)
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    if not program.roe.allow_oauth_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_oauth_probes"},
        )
        return

    if not program.roe.authorized_test_accounts:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_authorized_test_accounts"},
        )
        return

    if not os.environ.get(_FIXTURE_SECRET_ENV):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.MISSING_SECRET,
            details={"missing_secret": _FIXTURE_SECRET_ENV},
        )
        return

    target = target_run.target
    fixture_url = os.environ.get("FIXTURE_OAUTH_ACCOUNT_LINK_URL", target.base_url)
    base = fixture_url.rstrip("/")
    accounts = program.roe.authorized_test_accounts

    with httpx.Client(follow_redirects=False, timeout=10) as http:
        login = http.post(
            base + "/login",
            json={
                "username": accounts[0],
                "password": os.environ.get("FIXTURE_OAUTH_ACCOUNT_LINK_PASS_A", "pass-a"),
            },
        )
    if login.status_code != 200:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "fixture_login_failed"},
        )
        return
    session_headers = {"X-Session-Token": login.json().get("token", "")}

    for method, path, json_body, no_csrf_sent in _CANDIDATE_PROBES:
        acquire_for(program)
        # Use submit_probe to get raw httpx.Response with headers (needed for 302 Location)
        request_kwargs: dict = {"headers": session_headers}
        if json_body is not None:
            request_kwargs["json"] = json_body
        request = httpx.Request(
            method, base + path,
            **request_kwargs,
        )
        resp = submit_probe(request)
        if resp is None:
            record_refusal(
                scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
                reason=RefusalReason.TRANSPORT_ERROR,
                details={"detail": f"target_unreachable:{path}"},
            )
            return

        flaw = classify_link_flaw(
            resp,
            endpoint_url=base + path,
            no_csrf_sent=no_csrf_sent,
        )
        if flaw is not None:
            _emit_link_finding(
                scan_run=scan_run, target=target, flaw=flaw,
            )
            return


def _emit_link_finding(*, scan_run: "ScanRun", target: "ScanTarget", flaw) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=f"Account-linking flaw: {flaw.kind.value}",
        category="oauth_account_linking_flaws",
        severity=Severity.MEDIUM,
        confidence=flaw.confidence,
        status=FindingStatus.CANDIDATE,
        data={
            "kind": flaw.kind.value,
            "endpoint": flaw.endpoint_url,
            "method": flaw.http_method,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
