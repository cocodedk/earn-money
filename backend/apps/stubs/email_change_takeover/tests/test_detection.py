"""End-to-end detection tests for stub 2.9 (email-change-takeover)."""
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
from apps.stubs.email_change_takeover.runner import run


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
        ),
    )


def _wire(*, change_resp, login_token: str = "tok"):
    """Patch the full chain: register OK, login OK, token extracted,
    change-email returns the given response."""
    return [
        patch.object(get_registry(), "find_for_host",
                     return_value=_program()),
        patch("apps.stubs.email_change_takeover.runner.register_via_api",
              return_value=MagicMock(status_code=201)),
        patch("apps.stubs.email_change_takeover.runner.login_via_api",
              return_value=MagicMock(status_code=200)),
        patch("apps.stubs.email_change_takeover.runner.bearer_token_from",
              return_value=login_token),
        patch("apps.stubs.email_change_takeover.runner.change_email_unauthed_password",
              return_value=change_resp),
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
def test_change_email_200_emits_finding() -> None:
    """change-email returns 200 without current_password → Finding
    (HIGH, high, candidate, requires_manual_review)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.9")
    _run(scan_run, target_run, _wire(change_resp=MagicMock(status_code=200)))
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_email_change_takeover"
    assert f.severity == "high"
    assert f.confidence == "high"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["change_email_status"] == 200
    assert f.data["requires_manual_review"] is True
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_change_email_400_no_finding() -> None:
    """change-email returns 400 (re-auth required) → no Finding,
    no refusal event."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.9")
    _run(scan_run, target_run, _wire(change_resp=MagicMock(status_code=400)))
    assert not Finding.objects.filter(scan_run=scan_run).exists()
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    ).exists()
