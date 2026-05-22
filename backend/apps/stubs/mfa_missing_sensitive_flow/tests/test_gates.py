"""Gate tests for stub 2.11 (missing-mfa-on-sensitive-flows)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.mfa_missing_sensitive_flow.runner import run


def _program(
    *, allow_reg: bool = True, allow_login: bool = True,
    allow_mfa: bool = True,
) -> Program:
    return Program(
        platform="local", slug="reset-canary",
        scope=Scope(
            platform="local", slug="reset-canary",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_registration_probes=allow_reg,
            allow_active_login_probes=allow_login,
            allow_mfa_probes=allow_mfa,
        ),
    )


@pytest.mark.django_db
def test_roe_registration_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(allow_reg=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["knob"] == "allow_registration_probes"


@pytest.mark.django_db
def test_roe_login_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(allow_login=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["knob"] == "allow_active_login_probes"


@pytest.mark.django_db
def test_roe_mfa_disabled() -> None:
    """Codex P1.1 — 2.11 is part of the MFA family; allow_mfa_probes
    must gate it even when registration/login are permitted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(allow_mfa=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["knob"] == "allow_mfa_probes"


@pytest.mark.django_db
def test_register_unreachable() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.register_via_api",
               return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "register_endpoint_unreachable_or_rejected"


@pytest.mark.django_db
def test_login_unreachable() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.login_via_api",
               return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "login_endpoint_unreachable_or_rejected"


@pytest.mark.django_db
def test_login_no_token() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.login_via_api",
               return_value=MagicMock(status_code=200)), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.bearer_token_from",
               return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "login_response_yielded_no_token"


@pytest.mark.django_db
def test_sensitive_unreachable() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.11")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.login_via_api",
               return_value=MagicMock(status_code=200)), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.bearer_token_from",
               return_value="tok"), \
         patch("apps.stubs.mfa_missing_sensitive_flow.runner.post_sensitive_action",
               return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "sensitive_action_endpoint_unreachable"
