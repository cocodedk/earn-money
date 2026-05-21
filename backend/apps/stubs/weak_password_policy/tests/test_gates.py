"""Gate tests for stub 2.2 (weak-password-policy)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.weak_password_policy.runner import run


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
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(allow_registration=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "roe_disabled"
    assert ev.data["knob"] == "allow_registration_probes"


@pytest.mark.django_db
def test_all_transport_errors_emit_refusal() -> None:
    """register_via_api returns None for every candidate password →
    AUTH_PROBE_REFUSED reason=transport_error."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_password_policy.runner.register_via_api",
               return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "transport_error"
