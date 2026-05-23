"""Stub 3.3 runner — weak-samesite."""
from __future__ import annotations

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.session.cookie_parser import parse_set_cookie

from ..runners import guarded_runner
from .classify import SameSiteStatus, WeaknessKind, classify_cookie

_STUB_ID = "3.3"
_PROBE_PATHS = ("/", "/login")


@guarded_runner(_STUB_ID)
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    base = target_run.target.base_url.rstrip("/")
    seen: set[str] = set()
    for path in _PROBE_PATHS:
        resp = submit_probe(httpx.Request("GET", base + path))
        if resp is None:
            continue
        # X-Cookie-Role: sso signals the server allowlists this response's cookies
        # for cross-origin flows that legitimately require SameSite=None.
        sso_allowlisted = resp.headers.get("X-Cookie-Role", "").lower() == "sso"
        _process_response(
            resp, scan_run=scan_run, target_run=target_run,
            seen=seen, sso_allowlisted=sso_allowlisted,
        )


def _process_response(
    resp: httpx.Response, *, scan_run: ScanRun, target_run: ScanTargetRun,
    seen: set[str], sso_allowlisted: bool,
) -> None:
    for raw in resp.headers.get_list("Set-Cookie"):
        cookie = parse_set_cookie(raw)
        if cookie.name in seen:
            continue
        result = classify_cookie(cookie, sso_allowlisted=sso_allowlisted)
        if result.status in (SameSiteStatus.CONFIRMED, SameSiteStatus.CANDIDATE):
            seen.add(cookie.name)
            _emit_finding(
                scan_run=scan_run, target_run=target_run,
                cookie_name=cookie.name,
                raw_header=cookie.raw_set_cookie,
                status=result.status,
                confidence=result.confidence,
                weakness_kind=result.weakness_kind,
            )


def _emit_finding(
    *, scan_run: ScanRun, target_run: ScanTargetRun,
    cookie_name: str, raw_header: str, status: SameSiteStatus,
    confidence: str, weakness_kind: WeaknessKind | None,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run,
        target=target_run.target,
        stub_slug=_STUB_ID,
        title=f"Session cookie '{cookie_name}' has weak SameSite attribute",
        category="weak_samesite",
        severity=Severity.MEDIUM,
        confidence=confidence,
        status=FindingStatus.CONFIRMED if status is SameSiteStatus.CONFIRMED else FindingStatus.CANDIDATE,
        data={
            "cookie_name": cookie_name,
            "raw_set_cookie": raw_header,
            "weakness_kind": getattr(weakness_kind, "value", None),
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
