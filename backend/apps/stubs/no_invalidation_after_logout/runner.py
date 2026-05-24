"""Stub 3.7 runner — no session invalidation after logout."""
from __future__ import annotations

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe

from ..runners import guarded_runner
from .classify import InvalidationStatus, classify_invalidation

_STUB_ID = "3.7"
_SEED_PATH = "/invalidation/seed"
_CHECK_PATH = "/invalidation/check"
_LOGOUT_PATH = "/invalidation/logout-keeps-session"


@guarded_runner(_STUB_ID)
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    base = target_run.target.base_url.rstrip("/")

    seed_resp = submit_probe(httpx.Request("POST", base + _SEED_PATH))
    if seed_resp is None:
        return
    session_cookie = _extract_session_cookie(seed_resp)

    check_headers = {"Cookie": session_cookie} if session_cookie else {}
    pre_resp = submit_probe(httpx.Request("GET", base + _CHECK_PATH,
                                          headers=check_headers))
    if pre_resp is None or not (200 <= pre_resp.status_code < 300):
        return

    logout_resp = submit_probe(httpx.Request("POST", base + _LOGOUT_PATH,
                                             headers=check_headers))
    if logout_resp is None:
        return

    post_resp = submit_probe(httpx.Request("GET", base + _CHECK_PATH,
                                           headers=check_headers))
    if post_resp is None:
        return

    result = classify_invalidation(pre_resp.status_code, post_resp.status_code)
    if result.status is InvalidationStatus.CONFIRMED:
        _emit_finding(scan_run=scan_run, target_run=target_run, result=result)


def _extract_session_cookie(resp: httpx.Response) -> str:
    for raw in resp.headers.get_list("Set-Cookie"):
        name_val = raw.split(";", 1)[0].strip()
        if "=" in name_val and name_val.partition("=")[2]:
            return name_val
    return ""


def _emit_finding(
    *, scan_run: ScanRun, target_run: ScanTargetRun, result,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run,
        target=target_run.target,
        stub_slug=_STUB_ID,
        title="Session not invalidated after logout",
        category="no_invalidation_after_logout",
        severity=Severity.HIGH,
        confidence="high",
        status=FindingStatus.CONFIRMED,
        data={
            "pre_logout_status": result.pre_logout_status,
            "post_logout_status": result.post_logout_status,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
