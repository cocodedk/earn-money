"""Stub 2.2 runner — weak-password-policy (registration canary).

Detects registration endpoints that accept trivially weak passwords.
For each candidate weak password (short / common-word / numeric-only),
the runner submits one registration POST with a unique scanner-owned
synthetic email. The FIRST 2xx response is the positive signal —
that password class was accepted by the server.

Flow:
1. RoE gate (`allow_registration_probes`).
2. For each candidate password class:
   - Build a fresh synthetic email (so each attempt is a new account).
   - POST to the candidate register paths via `register_via_api`.
   - If status 2xx → emit Finding(category=auth_weak_password_policy)
     with which class was accepted; STOP (spec: stop after the first
     accepted weak password).
3. If every candidate yields non-2xx → no finding.
4. If every candidate yields None (transport error) → AUTH_PROBE_REFUSED
   transport_error.

No FIXTURE_TEST_PASSWORD gate — registration uses synthetic identities
end-to-end. No authorized_test_accounts gate either; the spec only
requires that real-user accounts are NOT used, which the synthetic
email guarantees.
"""
from __future__ import annotations

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.identifiers import generate_invalid_identifier
from apps.stubs._shared.auth.register import register_via_api
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.targets.models import ScanTarget

from ..runners import guarded_runner


_STUB_ID = "2.2"
_CATEGORY = "auth_weak_password_policy"

# Weak-password candidate classes per spec §"Active checks":
#   (class_name, sample). One sample per class — the runner does NOT
#   brute-force or iterate variants.
_WEAK_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("too_short", "a"),
    ("common_word", "password"),
    ("numeric_only", "12345678"),
)


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

    any_response_seen = False
    for class_name, candidate in _WEAK_CANDIDATES:
        synthetic_email = generate_invalid_identifier("email")
        resp = register_via_api(
            base_url=target.base_url,
            email=synthetic_email, password=candidate,
        )
        if resp is None:
            continue
        any_response_seen = True
        if 200 <= resp.status_code < 300:
            _emit_finding(
                scan_run=scan_run, target=target,
                accepted_class=class_name,
                accepted_status=resp.status_code,
            )
            return

    if not any_response_seen:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "register_endpoints_unreachable"},
        )


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget,
    accepted_class: str, accepted_status: int,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=f"Registration accepts {accepted_class} password",
        category=_CATEGORY,
        severity=Severity.MEDIUM,
        confidence="high",
        status=FindingStatus.CANDIDATE,
        data={
            "accepted_class": accepted_class,
            "accepted_status": accepted_status,
            "candidate_pattern": "scanner-*@example.invalid",
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
