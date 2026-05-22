"""Stub 2.19 runner — duplicate-account-confusion.

Detects targets whose registration endpoint leaks account existence:
* registering a NEW email → success (HTTP 2xx)
* registering an EXISTING email → distinct error response

Flow:
1. Gates: RoE allow_registration_probes, authorized accounts, password.
2. Issue one registration POST with a synthetic invalid identifier
   (the "new" probe).
3. Issue a second registration POST with the canary's existing
   identifier (the "existing" probe).
4. `normalize()` + `diff()` both responses.
5. Status / JSON-error / title differentiators present → Finding.

Targets covered by this MVP: HTTP-API style register endpoints
(Juice Shop `/api/Users`, generic JSON `POST /register`). HTML
form-based register flows are a follow-up — the spec is the same,
the request-construction layer differs.
"""
from __future__ import annotations

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.identifiers import generate_invalid_identifier
from apps.stubs._shared.auth.normalize import diff, normalize
from apps.stubs._shared.auth.register import register_via_api
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal

from ..runners import guarded_runner


# Both register POSTs use a throwaway password — the stub never
# tries to log in with these credentials. The detection signal is
# whether the registration RESPONSE differs between a new and an
# existing email, not whether the account can subsequently sign in.
# `FIXTURE_TEST_PASSWORD` is therefore NOT a prerequisite for 2.19;
# only RoE + authorized_test_accounts gate this stub.
_THROWAWAY_PASSWORD = "scanner-throwaway-passphrase"


@guarded_runner("2.19")
def run(
    scan_run: ScanRun, target_run: ScanTargetRun,
    *, program: Program,
) -> None:
    target = target_run.target
    if not program.roe.allow_registration_probes:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.19",
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_registration_probes"},
        )
        return
    if not program.roe.authorized_test_accounts:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.19",
            reason=RefusalReason.FIXTURE_REQUIRED,
            details={"detail": "no_authorized_test_accounts"},
        )
        return

    existing_email = program.roe.authorized_test_accounts[0]
    new_email = generate_invalid_identifier("email")

    resp_new = register_via_api(
        base_url=target.base_url,
        email=new_email,
        password=_THROWAWAY_PASSWORD,
    )
    resp_existing = register_via_api(
        base_url=target.base_url,
        email=existing_email,
        password=_THROWAWAY_PASSWORD,
    )

    if resp_new is None or resp_existing is None:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id="2.19",
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "register_endpoint_unreachable"},
        )
        return

    norm_new = normalize(resp_new)
    norm_existing = normalize(resp_existing)
    differentiators = diff(norm_new, norm_existing)

    if not differentiators:
        return  # no leak detected

    _emit_finding(
        scan_run=scan_run, target=target,
        new_email=new_email, existing_email=existing_email,
        differentiators=differentiators,
    )


def _emit_finding(
    *, scan_run, target, new_email, existing_email, differentiators,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.19",
        title="Registration endpoint leaks account existence",
        category="auth_duplicate_account_confusion",
        severity=Severity.MEDIUM,
        confidence="high" if len(differentiators) >= 2 else "medium",
        status=FindingStatus.CANDIDATE,
        data={
            "differentiators_count": len(differentiators),
            "differentiator_kinds": [d.kind for d in differentiators],
            # Identifiers are stub-controlled / fixture-known, safe to log.
            "new_email_pattern": "scanner-*@example.invalid",
            "existing_email_known": True,
        },
    )
    log_finding_candidate(finding, stub_id="2.19")
