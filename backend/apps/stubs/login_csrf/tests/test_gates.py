"""Gate tests for stub 2.18 (login-csrf)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.discovery import FetchOutcome
from apps.stubs._test_factories import seed_target_run
from apps.stubs.login_csrf.runner import run


def _program() -> Program:
    return Program(
        platform="local", slug="dvwa",
        scope=Scope(
            platform="local", slug="dvwa",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=10),
    )


@pytest.mark.django_db
def test_transport_error_refusal() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.18")
    outcome = FetchOutcome(
        ok=False, status=0, body="", content_type="",
        final_url="https://x.example", error="ConnectError",
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.login_csrf.runner.fetch_for_discovery",
               return_value=outcome):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "transport_error"


@pytest.mark.django_db
def test_out_of_scope_returns_silently() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.18")
    outcome = FetchOutcome(
        ok=True, status=200, body="<html></html>", content_type="text/html",
        final_url="https://attacker.example/landed", error=None,
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.login_csrf.runner.fetch_for_discovery",
               return_value=outcome):
        run(scan_run, target_run)
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_no_login_form_found() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.18")
    outcome = FetchOutcome(
        ok=True, status=200, body="<html><body>nothing</body></html>",
        content_type="text/html", final_url="https://x.example/", error=None,
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.login_csrf.runner.fetch_for_discovery",
               return_value=outcome):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_login_form_found"
