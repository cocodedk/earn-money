"""Gate tests for stub 2.13 (mfa-reset-abuse)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.mfa_reset_abuse.runner import run


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


_TARGET = "apps.stubs.mfa_reset_abuse.runner"


@pytest.mark.django_db
def test_roe_mfa_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(allow_mfa=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["knob"] == "allow_mfa_probes"


@pytest.mark.django_db
def test_roe_registration_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(allow_reg=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["knob"] == "allow_registration_probes"


@pytest.mark.django_db
def test_roe_login_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(allow_login=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["knob"] == "allow_active_login_probes"


@pytest.mark.django_db
def test_register_unreachable() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch(f"{_TARGET}.register_via_api", return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "register_endpoint_unreachable_or_rejected"


@pytest.mark.django_db
def test_login_unreachable() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch(f"{_TARGET}.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch(f"{_TARGET}.login_via_api", return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "login_endpoint_unreachable_or_rejected"


@pytest.mark.django_db
def test_login_no_token() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch(f"{_TARGET}.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch(f"{_TARGET}.login_via_api",
               return_value=MagicMock(status_code=200)), \
         patch(f"{_TARGET}.bearer_token_from", return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "login_response_yielded_no_token"


@pytest.mark.django_db
def test_enroll_unreachable() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch(f"{_TARGET}.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch(f"{_TARGET}.login_via_api",
               return_value=MagicMock(status_code=200)), \
         patch(f"{_TARGET}.bearer_token_from", return_value="tok"), \
         patch(f"{_TARGET}.enroll_mfa", return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "mfa_enroll_endpoint_unreachable_or_rejected"


@pytest.mark.django_db
def test_pre_state_unreachable() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch(f"{_TARGET}.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch(f"{_TARGET}.login_via_api",
               return_value=MagicMock(status_code=200)), \
         patch(f"{_TARGET}.bearer_token_from", return_value="tok"), \
         patch(f"{_TARGET}.enroll_mfa",
               return_value=MagicMock(status_code=200)), \
         patch(f"{_TARGET}.verify_mfa_enrolled", return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "mfa_state_endpoint_unreachable"


@pytest.mark.django_db
def test_enrollment_did_not_land() -> None:
    """Same guard as 2.10 — confirm enrollment landed before claiming
    the disable was a real reset abuse."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch(f"{_TARGET}.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch(f"{_TARGET}.login_via_api",
               return_value=MagicMock(status_code=200)), \
         patch(f"{_TARGET}.bearer_token_from", return_value="tok"), \
         patch(f"{_TARGET}.enroll_mfa",
               return_value=MagicMock(status_code=200)), \
         patch(f"{_TARGET}.verify_mfa_enrolled", return_value=False):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "mfa_enrollment_did_not_land"


@pytest.mark.django_db
def test_disable_unreachable() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.13")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch(f"{_TARGET}.register_via_api",
               return_value=MagicMock(status_code=201)), \
         patch(f"{_TARGET}.login_via_api",
               return_value=MagicMock(status_code=200)), \
         patch(f"{_TARGET}.bearer_token_from", return_value="tok"), \
         patch(f"{_TARGET}.enroll_mfa",
               return_value=MagicMock(status_code=200)), \
         patch(f"{_TARGET}.verify_mfa_enrolled", return_value=True), \
         patch(f"{_TARGET}.disable_mfa", return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "mfa_disable_endpoint_unreachable"
