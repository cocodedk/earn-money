"""Stub 3.2 runner — missing-secure."""
from __future__ import annotations

from urllib.parse import urlparse

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.session.cookie_parser import parse_set_cookie

from ..runners import guarded_runner
from .classify import SecureStatus, classify_cookie

_STUB_ID = "3.2"
_PROBE_PATHS = ("/", "/login")


@guarded_runner(_STUB_ID)
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    base = target_run.target.base_url.rstrip("/")
    scheme = urlparse(base).scheme
    seen: set[str] = set()
    for path in _PROBE_PATHS:
        resp = submit_probe(httpx.Request("GET", base + path))
        if resp is None:
            continue
        _process_response(
            resp, scan_run=scan_run, target_run=target_run,
            scheme=scheme, seen=seen,
        )


def _process_response(
    resp: httpx.Response, *, scan_run: ScanRun, target_run: ScanTargetRun,
    scheme: str, seen: set[str],
) -> None:
    for raw in resp.headers.get_list("Set-Cookie"):
        cookie = parse_set_cookie(raw)
        if cookie.name in seen:
            continue
        result = classify_cookie(cookie, scheme=scheme)
        if result.status in (SecureStatus.CONFIRMED, SecureStatus.CANDIDATE):
            seen.add(cookie.name)
            _emit_finding(
                scan_run=scan_run, target_run=target_run,
                cookie_name=cookie.name,
                raw_header=cookie.raw_set_cookie,
                status=result.status,
                confidence=result.confidence,
            )


def _emit_finding(
    *, scan_run: ScanRun, target_run: ScanTargetRun,
    cookie_name: str, raw_header: str, status: SecureStatus, confidence: str,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run,
        target=target_run.target,
        stub_slug=_STUB_ID,
        title=f"Session cookie '{cookie_name}' missing Secure attribute",
        category="missing_secure",
        severity=Severity.HIGH,
        confidence=confidence,
        status=FindingStatus.CONFIRMED if status is SecureStatus.CONFIRMED else FindingStatus.CANDIDATE,
        data={"cookie_name": cookie_name, "raw_set_cookie": raw_header},
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
