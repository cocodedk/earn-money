"""Stub 2.16 runner — oauth-token-substitution."""
from __future__ import annotations

import os

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.discovery import fetch_for_discovery
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.targets.models import ScanTarget

from ..runners import guarded_runner
from .classify import classify_passive_oauth_evidence
from .submit import run_substitution_test


_FIXTURE_SECRET_ENV = "FIXTURE_OAUTH_CLIENT_SECRET"
_STUB_ID = "2.16"


@guarded_runner("2.16")
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
    fixture_url = os.environ.get("FIXTURE_OAUTH_TOKEN_SUB_URL", target.base_url)
    accounts = program.roe.authorized_test_accounts

    # Passive discovery — FetchOutcome.final_url is the last URL after redirect-following
    acquire_for(program)
    resp = fetch_for_discovery(
        fixture_url + "/login",
        target=target, program=program,
    )
    if not resp.ok:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "target_unreachable"},
        )
        return

    # Adapt FetchOutcome to the classify interface (expects .url and .text)
    class _Adapter:
        url = resp.final_url
        text = resp.body

    evidence = classify_passive_oauth_evidence(_Adapter())

    # Active substitution test — only with two scanner-owned accounts
    if program.roe.allow_active_login_probes and len(accounts) >= 2:
        with httpx.Client(follow_redirects=False, timeout=10) as http:
            result = run_substitution_test(
                base_url=fixture_url,
                cred_a=(accounts[0], os.environ.get("FIXTURE_OAUTH_TOKEN_SUB_PASS_A", "pass-a")),
                cred_b=(accounts[1], os.environ.get("FIXTURE_OAUTH_TOKEN_SUB_PASS_B", "pass-b")),
                http=http,
            )
        if result.status in ("confirmed", "candidate") and result.substitution_attempted:
            _emit_token_sub_finding(
                scan_run=scan_run, target=target, result=result,
            )
            return

    # Fall back to passive candidate
    if evidence and evidence.detected:
        _emit_token_sub_finding(
            scan_run=scan_run, target=target,
            result=None, passive_evidence=evidence,
        )


def _emit_token_sub_finding(
    *, scan_run: "ScanRun", target: "ScanTarget",
    result=None, passive_evidence=None,
) -> None:
    if result and result.substitution_attempted:
        conf = result.confidence
        sev = Severity.HIGH if result.status == "confirmed" else Severity.MEDIUM
        data = {
            "artifact_kind": result.artifact_kind,
            "identity_mismatch": result.identity_mismatch_observed,
            "substitution_accepted": result.substitution_accepted,
            "requires_manual_review": result.status != "confirmed",
        }
    else:
        conf = "low"
        sev = Severity.INFO
        data = {
            "artifact_kind": passive_evidence.artifact_kind if passive_evidence else "unknown",
            "passive_only": True,
            "requires_manual_review": True,
        }
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title="OAuth token/code substitution possible",
        category="oauth_token_substitution",
        severity=sev,
        confidence=conf,
        status=FindingStatus.CANDIDATE,
        data=data,
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
