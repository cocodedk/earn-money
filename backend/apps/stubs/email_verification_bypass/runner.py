"""Stub 2.20 runner — email-verification-bypass.

Detects registration flows where a freshly-created account can
authenticate before the email address is verified. Two-step probe:
register a synthetic account, then immediately try to log in with
the same credentials. If login succeeds AND the registration
response indicated verification was required → confirmed-shape
finding. If login succeeds without explicit verification messaging
→ candidate (the system may simply have no verification at all).

Flow:
1. RoE gate (`allow_registration_probes`).
2. Generate one synthetic email + password.
3. `register_via_api` → if status is not 2xx, no finding (we never
   created an account).
4. `login_via_api` with the same credentials.
5. Classify login response:
   * status 2xx with session evidence (Set-Cookie OR token-like
     keyword in body) → session_issued.
   * otherwise → login_blocked.
6. If session_issued → Finding(category=auth_email_verification_bypass,
   severity=MEDIUM, confidence=medium, status=CANDIDATE,
   requires_manual_review=True).

No `authorized_test_accounts` gate — the stub uses synthetic
identifiers end-to-end and never touches a real account.
"""
from __future__ import annotations

import secrets

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.identifiers import generate_invalid_identifier
from apps.stubs._shared.auth.login import login_via_api
from apps.stubs._shared.auth.register import register_via_api
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.targets.models import ScanTarget

from ..runners import guarded_runner


_STUB_ID = "2.20"
_CATEGORY = "auth_email_verification_bypass"
_CONFIDENCE = "medium"

# Lowercase substrings that indicate a JWT-like or bearer access
# token in the login response body. Case-insensitive match — any
# hit means a session was issued.
_TOKEN_BODY_MARKERS: tuple[str, ...] = (
    '"token"',
    '"accesstoken"',
    '"access_token"',
    '"jwt"',
    '"authentication"',
    "bearer ",
)

# Verification-required text in the REGISTRATION response. Presence
# strengthens confidence (we have evidence the system DOES gate on
# verification but failed to enforce it). Both compact-JSON and
# whitespace-formatted variants ("k":v vs "k": v) are listed because
# json.dumps() defaults to the spaced form and runners can see either.
_VERIFY_REQUIRED_MARKERS: tuple[str, ...] = (
    "verify your email",
    "email verification",
    "confirmation email",
    "activate your account",
    "check your inbox",
    "account is inactive",
    "email not verified",
    '"requiresverification"',
    '"emailverified":false',
    '"emailverified": false',
    '"verified":false',
    '"verified": false',
    '"isverified":false',
    '"isverified": false',
    '"status":"pending"',
    '"status": "pending"',
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

    email = generate_invalid_identifier("email")
    password = f"scanner-evb-{secrets.token_hex(8)}"

    reg = register_via_api(
        base_url=target.base_url, email=email, password=password,
    )
    if reg is None or not (200 <= reg.status_code < 300):
        return

    login = login_via_api(
        base_url=target.base_url, email=email, password=password,
    )
    if login is None or not _is_session_issued(login):
        return

    verify_required = _registration_required_verification(reg)
    _emit_finding(
        scan_run=scan_run, target=target,
        login_status=login.status_code,
        verify_required=verify_required,
    )


def _is_session_issued(response) -> bool:  # type: ignore[no-untyped-def]
    """Login response carries session evidence: 2xx status AND
    (Set-Cookie OR a token-like body marker)."""
    if not (200 <= response.status_code < 300):
        return False
    headers = response.headers or {}
    for name in headers:
        if str(name).lower() == "set-cookie":
            return True
    body_lo = (response.text or "").lower()
    return any(marker in body_lo for marker in _TOKEN_BODY_MARKERS)


def _registration_required_verification(response) -> bool:  # type: ignore[no-untyped-def]
    """Did the REGISTRATION response indicate email verification is
    required? Used to upgrade confidence on the finding."""
    body_lo = (response.text or "").lower()
    return any(marker in body_lo for marker in _VERIFY_REQUIRED_MARKERS)


def _emit_finding(
    *, scan_run: ScanRun, target: ScanTarget,
    login_status: int, verify_required: bool,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=_STUB_ID,
        title=(
            "Unverified account can authenticate"
            if verify_required
            else "Synthetic account can authenticate; email-verification status unknown"
        ),
        category=_CATEGORY,
        severity=Severity.MEDIUM,
        confidence="high" if verify_required else _CONFIDENCE,
        status=FindingStatus.CANDIDATE,
        data={
            "login_status": login_status,
            "registration_required_verification": verify_required,
            "synthetic_email_pattern": "scanner-*@example.invalid",
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
