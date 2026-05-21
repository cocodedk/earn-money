"""Gate tests for stub 2.20 (email-verification-bypass)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.email_verification_bypass.runner import run


def _program(*, allow_registration: bool = True) -> Program:
    return Program(
        platform="local", slug="juice-shop",
        scope=Scope(
            platform="local", slug="juice-shop",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_registration_probes=allow_registration,
        ),
    )


@pytest.mark.django_db
def test_roe_disabled_emits_probe_refused() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(allow_registration=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "roe_disabled"


@pytest.mark.django_db
def test_registration_fails_silent_no_finding() -> None:
    """register_via_api returns None (transport-failed everywhere) →
    stub stops silently. No login attempted, no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=None), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api") as login_p:
        run(scan_run, target_run)
    login_p.assert_not_called()


@pytest.mark.django_db
def test_registration_4xx_no_finding() -> None:
    """Registration returns 400 (email taken / validation error) →
    no account exists → stub stops, no login attempted."""
    from unittest.mock import MagicMock
    reg = MagicMock(status_code=400, text="email taken")
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=reg), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api") as login_p:
        run(scan_run, target_run)
    login_p.assert_not_called()
