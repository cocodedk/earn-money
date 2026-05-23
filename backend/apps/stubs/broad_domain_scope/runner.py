"""Stub 3.4 runner — broad-domain-scope."""
from __future__ import annotations

from urllib.parse import urlparse

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.session.cookie_parser import parse_set_cookie

from ..runners import guarded_runner
from .classify import DomainStatus, ScopeIssue, classify_cookie

_STUB_ID = "3.4"
_PROBE_PATHS = ("/", "/login")


@guarded_runner(_STUB_ID)
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    base = target_run.target.base_url.rstrip("/")
    host = urlparse(base).hostname or target_run.target.host
    seen: set[str] = set()
    for path in _PROBE_PATHS:
        resp = submit_probe(httpx.Request("GET", base + path))
        if resp is None:
            continue
        sso_allowlisted = resp.headers.get("X-Cookie-Role", "").lower() == "sso"
        _process_response(
            resp, scan_run=scan_run, target_run=target_run,
            host=host, seen=seen, sso_allowlisted=sso_allowlisted,
        )


def _process_response(
    resp: httpx.Response, *, scan_run: ScanRun, target_run: ScanTargetRun,
    host: str, seen: set[str], sso_allowlisted: bool,
) -> None:
    for raw in resp.headers.get_list("Set-Cookie"):
        cookie = parse_set_cookie(raw)
        if cookie.name in seen:
            continue
        result = classify_cookie(cookie, host=host, sso_allowlisted=sso_allowlisted)
        if result.status in (DomainStatus.CONFIRMED, DomainStatus.CANDIDATE):
            seen.add(cookie.name)
            _emit_finding(
                scan_run=scan_run, target_run=target_run,
                cookie_name=cookie.name,
                raw_header=cookie.raw_set_cookie,
                status=result.status,
                confidence=result.confidence,
                scope_issue=result.scope_issue,
            )


def _emit_finding(
    *, scan_run: ScanRun, target_run: ScanTargetRun,
    cookie_name: str, raw_header: str, status: DomainStatus,
    confidence: str, scope_issue: ScopeIssue | None,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run,
        target=target_run.target,
        stub_slug=_STUB_ID,
        title=f"Session cookie '{cookie_name}' has overly broad Domain scope",
        category="broad_domain_scope",
        severity=Severity.MEDIUM,
        confidence=confidence,
        status=FindingStatus.CONFIRMED if status is DomainStatus.CONFIRMED else FindingStatus.CANDIDATE,
        data={
            "cookie_name": cookie_name,
            "raw_set_cookie": raw_header,
            "scope_issue": getattr(scope_issue, "value", None),
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
