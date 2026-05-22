"""End-to-end detection tests for stub 2.13 (mfa-reset-abuse)."""
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
from apps.stubs.mfa_reset_abuse.runner import run


_TARGET = "apps.stubs.mfa_reset_abuse.runner"


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


def _wire(*, disable_resp, pre_state: bool = True,
          post_state: bool | None = False):
    return [
        patch.object(get_registry(), "find_for_host", return_value=_program()),
        patch(f"{_TARGET}.register_via_api",
              return_value=MagicMock(status_code=201)),
        patch(f"{_TARGET}.login_via_api",
              return_value=MagicMock(status_code=200)),
        patch(f"{_TARGET}.bearer_token_from", return_value="tok"),
        patch(f"{_TARGET}.enroll_mfa",
              return_value=MagicMock(status_code=200)),
        # First call returns pre_state; second call returns post_state.
        patch(f"{_TARGET}.verify_mfa_enrolled",
              side_effect=[pre_state, post_state]),
        patch(f"{_TARGET}.disable_mfa", return_value=disable_resp),
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
def test_no_step_up_disable_emits_finding() -> None:
    """MFA enrolled → /mfa/disable returns 200 → post-call /me
    confirms mfaEnabled=false → Finding(reset_abuse, HIGH, high)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    _run(scan_run, target_run, _wire(
        disable_resp=MagicMock(status_code=200),
        pre_state=True, post_state=False,
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_mfa_reset_abuse"
    assert f.severity == "high"
    assert f.confidence == "high"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["disable_endpoint_status"] == 200
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_disable_403_no_finding() -> None:
    """Disable endpoint returns 403 (step-up required) → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    _run(scan_run, target_run, _wire(
        disable_resp=MagicMock(status_code=403),
        pre_state=True, post_state=True,
    ))
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_disable_2xx_but_state_still_enabled_no_finding() -> None:
    """Disable endpoint claims success but post-check shows mfa
    still on (endpoint returned 2xx without actually disabling) →
    no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    _run(scan_run, target_run, _wire(
        disable_resp=MagicMock(status_code=200),
        pre_state=True, post_state=True,
    ))
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_disable_2xx_but_post_state_endpoint_unreachable_no_finding() -> None:
    """Disable 2xx but post-state check returns None → we can't
    confirm the disable landed → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    _run(scan_run, target_run, _wire(
        disable_resp=MagicMock(status_code=200),
        pre_state=True, post_state=None,
    ))
    assert not Finding.objects.filter(scan_run=scan_run).exists()
