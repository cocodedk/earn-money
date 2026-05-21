"""Gate tests for stub 2.8 (reset-poisoning)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.mailbox import MailboxConfigError
from apps.stubs._test_factories import seed_target_run
from apps.stubs.predictable_reset_token.discovery import DiscoveryOutcome
from apps.stubs.reset_poisoning.runner import run


def _program(*, knob_on: bool = True, accounts: list[str] | None = None) -> Program:
    return Program(
        platform="local", slug="reset-canary",
        scope=Scope(
            platform="local", slug="reset-canary",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_password_reset_probes=knob_on,
            authorized_test_accounts=accounts or [],
        ),
    )


@pytest.mark.django_db
def test_roe_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(knob_on=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "roe_disabled"


@pytest.mark.django_db
def test_no_authorized_accounts() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=[])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_authorized_test_accounts"


@pytest.mark.django_db
def test_mailbox_unconfigured() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_poisoning.runner.load_mailbox_backend",
               side_effect=MailboxConfigError("nope")):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "mailbox_unconfigured"


@pytest.mark.django_db
def test_discovery_transport_error() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_poisoning.runner.load_mailbox_backend",
               return_value=MagicMock()), \
         patch("apps.stubs.reset_poisoning.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=None, final_url="https://x.example",
                   error="ConnectError",
               )):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "transport_error"


@pytest.mark.django_db
def test_no_reset_form_found() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_poisoning.runner.load_mailbox_backend",
               return_value=MagicMock()), \
         patch("apps.stubs.reset_poisoning.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=None, final_url="https://x.example/", error=None,
               )):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_reset_form_found"


@pytest.mark.django_db
def test_out_of_scope_final_url_returns_silently() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_poisoning.runner.load_mailbox_backend",
               return_value=MagicMock()), \
         patch("apps.stubs.reset_poisoning.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=MagicMock(action_url="https://attacker.example/"),
                   final_url="https://attacker.example/reset", error=None,
               )):
        run(scan_run, target_run)
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()
