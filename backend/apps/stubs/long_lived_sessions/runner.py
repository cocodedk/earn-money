"""Stub 3.8 runner — long-lived sessions."""
from __future__ import annotations

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.session.cookie_parser import parse_set_cookie

from ..runners import guarded_runner
from .classify import LongLivedStatus, classify_cookie

_STUB_ID = "3.8"
_PROBE_PATHS = ("/", "/lifetime/session-cookie-long")


@guarded_runner(_STUB_ID)
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    base = target_run.target.base_url.rstrip("/")
    seen: set[str] = set()
    for path in _PROBE_PATHS:
        resp = submit_probe(httpx.Request("GET", base + path))
        if resp is None:
            continue
        _process_response(resp, scan_run=scan_run, target_run=target_run, seen=seen)


def _process_response(
    resp: httpx.Response, *, scan_run: ScanRun, target_run: ScanTargetRun,
    seen: set[str],
) -> None:
    for raw in resp.headers.get_list("Set-Cookie"):
        cookie = parse_set_cookie(raw)
        if cookie.name in seen:
            continue
        result = classify_cookie(cookie)
        if result.status is LongLivedStatus.CONFIRMED:
            seen.add(cookie.name)
            _emit_finding(scan_run=scan_run, target_run=target_run, result=result)


def _emit_finding(
    *, scan_run: ScanRun, target_run: ScanTargetRun, result,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run,
        target=target_run.target,
        stub_slug=_STUB_ID,
        title=f"Session cookie '{result.cookie_name}' has excessive lifetime",
        category="long_lived_sessions",
        severity=Severity.MEDIUM,
        confidence="high",
        status=FindingStatus.CONFIRMED,
        data={
            "cookie_name": result.cookie_name,
            "observed_max_age": result.observed_max_age,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
