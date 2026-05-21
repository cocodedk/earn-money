"""Gate tests for stub 2.3 (missing-lockout)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.missing_lockout.runner import run
from apps.stubs._shared.auth.discovery import FetchOutcome


def _program(*, knob_on: bool = True, accounts: list[str] | None = None) -> Program:
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_active_login_probes=knob_on,
            authorized_test_accounts=accounts or [],
        ),
    )


@pytest.mark.django_db
def test_roe_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(knob_on=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["reason"] == "roe_disabled"


@pytest.mark.django_db
def test_no_authorized_accounts() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=[])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_authorized_test_accounts"


@pytest.mark.django_db
def test_transport_error_refusal() -> None:
    """fetch_for_discovery transport-fails → AUTH_PROBE_REFUSED."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    outcome = FetchOutcome(
        ok=False, status=0, body="", content_type="",
        final_url="https://x.example", error="ConnectError",
    )
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.missing_lockout.runner.fetch_for_discovery",
               return_value=outcome):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "transport_error"


@pytest.mark.django_db
def test_no_login_form_found() -> None:
    """Discovery returns no login form → AUTH_FIXTURE_REQUIRED."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    outcome = FetchOutcome(
        ok=True, status=200, body="<html><body>nothing here</body></html>",
        content_type="text/html", final_url="https://x.example/", error=None,
    )
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.missing_lockout.runner.fetch_for_discovery",
               return_value=outcome):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_login_form_found"


@pytest.mark.django_db
def test_non_login_form_present_is_skipped() -> None:
    """Body has an auth form but it's a password-reset (not a login)
    → `_pick_login_form` returns None after iterating, runner emits
    AUTH_FIXTURE_REQUIRED with detail=no_login_form_found."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    search_only = (
        "<html><body>"
        "<form action='/forgot-password' method='POST'>"
        "<input type='email' name='email'>"
        "</form></body></html>"
    )
    outcome = FetchOutcome(
        ok=True, status=200, body=search_only,
        content_type="text/html", final_url="https://x.example/", error=None,
    )
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.missing_lockout.runner.fetch_for_discovery",
               return_value=outcome):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_login_form_found"


@pytest.mark.django_db
def test_out_of_scope_final_url_returns_silently() -> None:
    """fetch_for_discovery's `final_url` resolves outside scope →
    `enforce_scope` raises OutOfScope and the runner returns without
    emitting AUTH_FINDING_CANDIDATE."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    outcome = FetchOutcome(
        ok=True, status=200, body="<html><body>ok</body></html>",
        content_type="text/html",
        final_url="https://attacker.example/landed",
        error=None,
    )
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.missing_lockout.runner.fetch_for_discovery",
               return_value=outcome):
        run(scan_run, target_run)
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()
