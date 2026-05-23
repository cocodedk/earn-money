"""Stub 3.11 — JWT missing-expiry runner."""
from __future__ import annotations

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.jwt_utils import fingerprint_token, parse_jwt, redact_token
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs.jwt_missing_expiry.classify import ExpiryStatus, classify_jwt_expiry
from apps.stubs.runners import guarded_runner

_STUB_ID = "3.11-jwt-missing-expiry"
_PROBE_PATHS = ("/",)
_TOKEN_BODY_KEYS = ("access_token", "id_token", "token")
_KIND_MAP = {
    "access_token": "access_token",
    "id_token": "id_token",
    "token": "access_token",
}
_STATUS_MAP = {
    ExpiryStatus.CONFIRMED: FindingStatus.CONFIRMED,
    ExpiryStatus.CANDIDATE: FindingStatus.CANDIDATE,
}
_SEVERITY_MAP = {
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
}


@guarded_runner(_STUB_ID)
def run(scan_run, target_run):
    base = target_run.target.base_url.rstrip("/")
    for path in _PROBE_PATHS:
        resp = submit_probe(httpx.Request("GET", base + path))
        if resp is None:
            continue
        _process_response(resp, scan_run, target_run)


def _process_response(resp, scan_run, target_run):
    tokens = _collect_tokens(resp)
    for raw_token, kind in tokens:
        parsed = parse_jwt(raw_token)
        if parsed is None:
            continue
        result = classify_jwt_expiry(parsed, token_kind=kind)
        if result.status in (ExpiryStatus.CONFIRMED, ExpiryStatus.CANDIDATE):
            _emit(raw_token, kind, result, scan_run, target_run)


def _collect_tokens(resp) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    auth = (resp.headers or {}).get("Authorization", "")
    if auth.startswith("Bearer "):
        tokens.append((auth[7:].strip(), "access_token"))
    try:
        body = resp.json()
        if isinstance(body, dict):
            for key in _TOKEN_BODY_KEYS:
                val = body.get(key)
                if isinstance(val, str) and "." in val:
                    tokens.append((val, _KIND_MAP.get(key, "unknown_jwt")))
    except Exception:
        pass
    return tokens


def _emit(raw_token: str, kind: str, result, scan_run, target_run):
    finding = Finding.objects.create(
        scan_run=scan_run,
        target=target_run.target,
        stub_slug=_STUB_ID,
        title="JWT missing expiry claim",
        category="jwt_missing_expiry",
        severity=_SEVERITY_MAP.get(result.confidence, Severity.LOW),
        confidence=result.confidence,
        status=_STATUS_MAP.get(result.status, FindingStatus.CANDIDATE),
        data={
            "token_kind": kind,
            "token_fingerprint": fingerprint_token(raw_token),
            "token_redacted": redact_token(raw_token),
            "exp": result.exp,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
