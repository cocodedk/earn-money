"""End-to-end detection tests for stub 2.11 (missing-mfa-on-
sensitive-flows)."""
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
from apps.stubs.mfa_missing_sensitive_flow.runner import run


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


def _wire(*, sensitive_resp):
    return [
        patch.object(get_registry(), "find_for_host", return_value=_program()),
        patch("apps.stubs.mfa_missing_sensitive_flow.runner.register_via_api",
              return_value=MagicMock(status_code=201)),
        patch("apps.stubs.mfa_missing_sensitive_flow.runner.login_via_api",
              return_value=MagicMock(status_code=200)),
        patch("apps.stubs.mfa_missing_sensitive_flow.runner.bearer_token_from",
              return_value="tok"),
        patch("apps.stubs.mfa_missing_sensitive_flow.runner.post_sensitive_action",
              return_value=sensitive_resp),
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
def test_sensitive_200_emits_finding() -> None:
    """Sensitive endpoint returns 200 without prior MFA enrollment
    → Finding(missing_mfa, MEDIUM, low)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    _run(scan_run, target_run, _wire(
        sensitive_resp=MagicMock(status_code=200),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_mfa_missing_sensitive_flow"
    assert f.severity == "medium"
    assert f.confidence == "low"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["sensitive_action_status"] == 200
    assert f.data["requires_manual_review"] is True
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_sensitive_403_no_finding() -> None:
    """403 (MFA required) → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    _run(scan_run, target_run, _wire(
        sensitive_resp=MagicMock(status_code=403),
    ))
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_sensitive_401_no_finding() -> None:
    """401 unauthorized → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    _run(scan_run, target_run, _wire(
        sensitive_resp=MagicMock(status_code=401),
    ))
    assert not Finding.objects.filter(scan_run=scan_run).exists()
