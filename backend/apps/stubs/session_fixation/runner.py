"""Stub 3.5 runner — session fixation."""
from __future__ import annotations

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.session.cookie_parser import parse_set_cookie

from ..runners import guarded_runner
from .classify import FixationStatus, classify_fixation

_STUB_ID = "3.5"
_LOGIN_PATH = "/fixation/login-vulnerable"


@guarded_runner(_STUB_ID)
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    base = target_run.target.base_url.rstrip("/")
    get_resp = submit_probe(httpx.Request("GET", base + _LOGIN_PATH))
    if get_resp is None:
        return
    pre_cookies = [
        parse_set_cookie(raw)
        for raw in get_resp.headers.get_list("Set-Cookie")
    ]
    post_resp = submit_probe(
        httpx.Request("POST", base + _LOGIN_PATH,
                      content=b"username=user&password=pass",
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    )
    if post_resp is None:
        return
    post_cookies = [
        parse_set_cookie(raw)
        for raw in post_resp.headers.get_list("Set-Cookie")
    ]
    result = classify_fixation(pre_cookies, post_cookies)
    if result.status is FixationStatus.CONFIRMED:
        _emit_finding(scan_run=scan_run, target_run=target_run,
                      affected_names=result.affected_names)


def _emit_finding(
    *, scan_run: ScanRun, target_run: ScanTargetRun,
    affected_names: list[str],
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run,
        target=target_run.target,
        stub_slug=_STUB_ID,
        title="Session fixation: session ID not rotated after login",
        category="session_fixation",
        severity=Severity.HIGH,
        confidence="high",
        status=FindingStatus.CONFIRMED,
        data={"affected_names": affected_names},
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
