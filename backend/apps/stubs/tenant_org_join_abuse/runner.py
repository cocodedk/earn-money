"""Stub 2.22 runner — tenant-org-join-abuse."""
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
from .classify import classify_join_success


_FIXTURE_SECRET_ENV = "FIXTURE_TENANT_ID"
_FIXTURE_URL_ENV = "FIXTURE_TENANT_LAB_URL"
_STUB_ID = "2.22"


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

    tenant_id = os.environ.get(_FIXTURE_SECRET_ENV)
    if not tenant_id:
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
            json={"username": accounts[0], "password": "pass-outside"},
        )
    if login.status_code != 200:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "fixture_login_failed"},
        )
        return
    session_headers = {"X-Session-Token": login.json().get("token", "")}

    # Probe 1: surface discovery — workspace dashboard
    acquire_for(program)
    surface_req = httpx.Request(
        "GET", f"{base}/workspace/{tenant_id}", headers=session_headers,
    )
    surface_resp = submit_probe(surface_req)
    if surface_resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": f"target_unreachable:/workspace/{tenant_id}"},
        )
        return

    # Probe 2: attempt unauthorized join
    join_url = f"{base}/api/workspaces/{tenant_id}/join"
    acquire_for(program)
    join_req = httpx.Request("POST", join_url, headers=session_headers)
    join_resp = submit_probe(join_req)
    if join_resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": f"target_unreachable:{join_url}"},
        )
        return

    flaw = classify_join_success(join_resp, join_url, tenant_id=tenant_id)
    if flaw is not None:
        _emit_finding(scan_run=scan_run, target=target, flaw=flaw, tenant_id=tenant_id)


def _emit_finding(
    *, scan_run: "ScanRun", target: "ScanTarget", flaw: object, tenant_id: str,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=f"Tenant/org join abuse: {flaw.kind.value}",  # type: ignore[attr-defined]
        category="tenant_org_join_abuse",
        severity=Severity.HIGH,
        confidence=flaw.confidence,  # type: ignore[attr-defined]
        status=FindingStatus.CANDIDATE,
        data={
            "kind": flaw.kind.value,  # type: ignore[attr-defined]
            "endpoint": flaw.endpoint_url,  # type: ignore[attr-defined]
            "method": flaw.http_method,  # type: ignore[attr-defined]
            "tenant_id": tenant_id,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
