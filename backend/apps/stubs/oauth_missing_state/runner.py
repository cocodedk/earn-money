"""Stub 2.15 runner — oauth-missing-state."""
from __future__ import annotations

import os
from urllib.parse import urljoin

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
from .classify import inspect_authorization_url


_FIXTURE_SECRET_ENV = "FIXTURE_OAUTH_CLIENT_SECRET"
_STUB_ID = "2.15"


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
    fixture_url = os.environ.get("FIXTURE_OAUTH_STATE_MISSING_URL", target.base_url)
    base = fixture_url.rstrip("/")
    acquire_for(program)
    # Missing-state detection must inspect the first 302 Location; do not follow redirects.
    request = httpx.Request("GET", base + "/auth/example")
    resp = submit_probe(request)
    if resp is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "target_unreachable"},
        )
        return

    authorization_url = resp.headers.get("Location", "")
    if not authorization_url:
        return
    authorization_url = urljoin(base + "/", authorization_url)

    inspection = inspect_authorization_url(authorization_url)
    if not inspection.is_oauth_authorization_request or inspection.has_state:
        return

    _emit_finding(
        scan_run=scan_run, target=target,
        authorization_url=authorization_url,
        confidence=inspection.confidence,
    )


def _emit_finding(
    *, scan_run: "ScanRun", target: "ScanTarget",
    authorization_url: str, confidence: str,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="OAuth authorization request missing state parameter",
        category="oauth_state_missing",
        severity=Severity.MEDIUM,
        confidence=confidence,
        status=FindingStatus.CANDIDATE,
        data={"authorization_url": authorization_url, "requires_manual_review": True},
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
