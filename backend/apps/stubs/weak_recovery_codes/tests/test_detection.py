"""End-to-end detection tests for stub 2.12 (weak-recovery-codes)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.weak_recovery_codes.runner import run


_TARGET = "apps.stubs.weak_recovery_codes.runner"


def _program() -> Program:
    return Program(
        platform="local", slug="reset-canary",
        scope=Scope(
            platform="local", slug="reset-canary",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_registration_probes=True,
            allow_active_login_probes=True,
            allow_mfa_probes=True,
        ),
    )


def _wire(codes: list[str]):
    return [
        patch.object(get_registry(), "find_for_host", return_value=_program()),
        patch(f"{_TARGET}.register_via_api",
              return_value=MagicMock(status_code=201)),
        patch(f"{_TARGET}.login_via_api",
              return_value=MagicMock(status_code=200)),
        patch(f"{_TARGET}.bearer_token_from", return_value="tok"),
        patch(f"{_TARGET}.enroll_mfa",
              return_value=MagicMock(status_code=200)),
        patch(f"{_TARGET}.generate_recovery_codes",
              return_value=MagicMock(status_code=200)),
        patch(f"{_TARGET}.extract_codes_from", return_value=codes),
    ]


def _run(scan_run, target_run, patches):
    for p in patches:
        p.start()
    try:
        run(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()


@pytest.mark.django_db
def test_sequential_codes_emit_critical_finding() -> None:
    """Codes are sequential integers (`1000`...`1007`) → analyse_
    tokens verdict=predictable signal=sequential_integer severity=
    critical → Finding emitted with severity CRITICAL."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.12")
    codes = [str(1000 + i) for i in range(8)]
    _run(scan_run, target_run, _wire(codes))
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_weak_recovery_codes"
    assert f.severity == "critical"
    assert f.confidence == "high"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["verdict"] == "predictable"
    assert f.data["signal"] == "sequential_integer"
    assert f.data["sample_size"] == 8
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_random_codes_no_finding() -> None:
    """analyse_tokens verdict=random → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.12")
    # 8 cryptographically-distinct strings — verdict=random.
    import secrets as _secrets
    codes = [_secrets.token_urlsafe(16) for _ in range(8)]
    _run(scan_run, target_run, _wire(codes))
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_inconclusive_too_few_no_finding() -> None:
    """Need ≥2 codes for analysis; with exactly 2 random codes the
    verdict can still be inconclusive — no Finding either way."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.12")
    import secrets as _secrets
    codes = [_secrets.token_urlsafe(16) for _ in range(2)]
    _run(scan_run, target_run, _wire(codes))
    # Verdict random or inconclusive → no Finding in both cases.
    assert not Finding.objects.filter(scan_run=scan_run).exists()
