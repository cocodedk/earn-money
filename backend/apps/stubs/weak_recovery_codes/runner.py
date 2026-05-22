"""Stub 2.12 runner — weak MFA recovery codes.

After MFA enrollment, the target hands out a small set of recovery
codes the user can present in place of a TOTP. Weak codes — short,
all-numeric, sequential, shared-prefix — make recovery-code
guessing as effective as no MFA at all.

Detection chain:
1. RoE gates: `allow_registration_probes` + `allow_active_login_
   probes` + `allow_mfa_probes`.
2. Register a scanner-owned synthetic account.
3. Log in to get a bearer token.
4. POST `/mfa/enroll` (candidate paths) to enable MFA.
5. POST `/mfa/recovery-codes/generate` (candidate paths) to fetch
   the recovery codes the canary issues post-enrollment.
6. Parse the codes from the response body (top-level `codes`,
   `recovery_codes`, `recoveryCodes`, or any list of strings
   inside the JSON).
7. Run `analyse_tokens()` (reused from stub 2.5) over the codes.
8. If the verdict is `predictable` → Finding(category=
   auth_weak_recovery_codes, severity inherited from the analysis
   — `critical` / `medium` / `high` map directly).

`random` / `inconclusive` verdicts → no Finding.
"""
from __future__ import annotations

import secrets

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.identifiers import generate_invalid_identifier
from apps.stubs._shared.auth.login import login_via_api
from apps.stubs._shared.auth.register import register_via_api
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.auth.token_analysis import analyse_tokens
from apps.targets.models import ScanTarget

from ..email_change_takeover.submit import bearer_token_from
from ..mfa_bypass.submit import enroll_mfa
from ..runners import guarded_runner
from .submit import extract_codes_from, generate_recovery_codes


_STUB_ID = "2.12"
_CATEGORY = "auth_weak_recovery_codes"
_SEVERITY_BY_ANALYSIS: dict[str, Severity] = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
}


@guarded_runner(_STUB_ID)
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    target = target_run.target
    if not program.roe.allow_registration_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_registration_probes"},
        )
        return
    if not program.roe.allow_active_login_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_active_login_probes"},
        )
        return
    if not program.roe.allow_mfa_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_mfa_probes"},
        )
        return

    canary_email = generate_invalid_identifier("email")
    canary_password = f"scanner-rc-{secrets.token_hex(8)}"

    acquire_for(program)
    reg = register_via_api(
        base_url=target.base_url,
        email=canary_email, password=canary_password,
    )
    if reg is None or not (200 <= reg.status_code < 300):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "register_endpoint_unreachable_or_rejected"},
        )
        return

    acquire_for(program)
    login = login_via_api(
        base_url=target.base_url,
        email=canary_email, password=canary_password,
    )
    if login is None or not (200 <= login.status_code < 300):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "login_endpoint_unreachable_or_rejected"},
        )
        return

    token = bearer_token_from(login)
    if token is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "login_response_yielded_no_token"},
        )
        return

    acquire_for(program)
    enroll = enroll_mfa(base_url=target.base_url, bearer_token=token)
    if enroll is None or not (200 <= enroll.status_code < 300):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "mfa_enroll_endpoint_unreachable_or_rejected"},
        )
        return

    acquire_for(program)
    codes_resp = generate_recovery_codes(
        base_url=target.base_url, bearer_token=token,
    )
    if codes_resp is None or not (200 <= codes_resp.status_code < 300):
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "recovery_codes_endpoint_unreachable_or_rejected"},
        )
        return

    codes = extract_codes_from(codes_resp)
    if len(codes) < 2:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "recovery_codes_response_yielded_no_codes"},
        )
        return

    # Codex MFA-family P2: duplicates are a weak-code signal that
    # `analyse_tokens` doesn't surface (eight copies of the same
    # value pass its random heuristic). Apply the recovery-code-
    # specific check first; fall through to the shared analyser
    # for sequential/prefix/low-entropy patterns.
    duplicates = len(codes) - len(set(codes))
    if duplicates > 0:
        _emit_duplicate_finding(
            scan_run=scan_run, target=target, sample_size=len(codes),
            duplicate_count=duplicates,
        )
        return

    analysis = analyse_tokens(codes)
    if analysis.verdict != "predictable":
        return  # Codes look random → safe.

    _emit_finding(
        scan_run=scan_run, target=target, analysis=analysis,
        sample_size=len(codes),
    )


def _emit_duplicate_finding(
    *, scan_run: ScanRun, target: ScanTarget,
    sample_size: int, duplicate_count: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=f"Recovery codes contain {duplicate_count} duplicate(s)",
        category=_CATEGORY,
        severity=Severity.HIGH,
        confidence="high",
        status=FindingStatus.CANDIDATE,
        data={
            "verdict": "predictable",
            "signal": "duplicate_codes",
            "duplicate_count": duplicate_count,
            "sample_size": sample_size,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget,
    analysis, sample_size: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=f"Recovery codes are {analysis.signal}",
        category=_CATEGORY,
        severity=_SEVERITY_BY_ANALYSIS.get(
            analysis.severity, Severity.MEDIUM,
        ),
        confidence="high",
        status=FindingStatus.CANDIDATE,
        data={
            "verdict": analysis.verdict,
            "signal": analysis.signal,
            "analyser_severity": analysis.severity,
            "sample_size": sample_size,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
