"""Gate tests for stub 2.6 (reset-token-reuse)."""
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
from apps.stubs.reset_token_reuse.runner import run


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


@pytest.fixture(autouse=True)
def _replacement_password_default(monkeypatch) -> None:
    """Codex P1 — runner now requires FIXTURE_RESET_REPLACEMENT_
    PASSWORD env var. Set a dummy by default; the dedicated
    `test_missing_replacement_password` overrides via `delenv`."""
    monkeypatch.setenv("FIXTURE_RESET_REPLACEMENT_PASSWORD", "x")
    monkeypatch.setenv("FIXTURE_RESET_REPLACEMENT_PASSWORD_2", "y")


@pytest.mark.django_db
def test_missing_replacement_password(monkeypatch) -> None:
    """Without FIXTURE_RESET_REPLACEMENT_PASSWORD set, the runner
    refuses (MISSING_SECRET) so it never resets the canary to a
    value the operator doesn't know (codex P1)."""
    monkeypatch.delenv("FIXTURE_RESET_REPLACEMENT_PASSWORD", raising=False)
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["reason"] == "missing_fixture_secret"
    assert ev.data["missing_secret"] == "FIXTURE_RESET_REPLACEMENT_PASSWORD"


@pytest.mark.django_db
def test_missing_replay_password(monkeypatch) -> None:
    """Without FIXTURE_RESET_REPLACEMENT_PASSWORD_2, the runner
    refuses — without it the second consumption either reuses the
    first password (suppressed by "new must differ" policy) or has
    to derive a value that may violate target charset/length
    constraints. Codex pass-3 P2."""
    monkeypatch.delenv("FIXTURE_RESET_REPLACEMENT_PASSWORD_2", raising=False)
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["missing_secret"] == "FIXTURE_RESET_REPLACEMENT_PASSWORD_2"


@pytest.mark.django_db
def test_roe_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(knob_on=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "roe_disabled"


@pytest.mark.django_db
def test_no_authorized_accounts() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=[])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_authorized_test_accounts"


@pytest.mark.django_db
def test_mailbox_unconfigured() -> None:
    """`load_mailbox_backend` raises MailboxConfigError → AUTH_
    FIXTURE_REQUIRED detail=mailbox_unconfigured."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               side_effect=MailboxConfigError("not configured")):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "mailbox_unconfigured"


@pytest.mark.django_db
def test_discovery_transport_error() -> None:
    """fetch_and_find_reset_form transport-fails → AUTH_PROBE_REFUSED."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=MagicMock()), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=None, final_url="https://x.example",
                   error="ConnectError",
               )):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED)
    assert ev.data["reason"] == "transport_error"


@pytest.mark.django_db
def test_out_of_scope_final_url_returns_silently() -> None:
    """fetch_and_find_reset_form's final_url is off-scope → enforce_
    scope raises OutOfScope, runner returns silently."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=MagicMock()), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=MagicMock(action_url="https://attacker.example/"),
                   final_url="https://attacker.example/reset", error=None,
               )):
        run(scan_run, target_run)
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_off_scope_form_action_url_returns_silently() -> None:
    """final_url is in-scope but form.action_url is off-scope
    (e.g. SSO/IdP-style absolute action) → enforce_scope on the
    action URL raises OutOfScope, runner returns without posting
    the reset request (codex P1)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=MagicMock()), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=MagicMock(action_url="https://attacker.example/forgot"),
                   final_url="https://x.example/", error=None,
               )):
        run(scan_run, target_run)
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
    ).exists()


@pytest.mark.django_db
def test_no_reset_form_found() -> None:
    """Discovery returns no reset form → AUTH_FIXTURE_REQUIRED."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=MagicMock()), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=None, final_url="https://x.example/", error=None,
               )):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_reset_form_found"


@pytest.mark.django_db
def test_mailbox_backend_returns_none_emits_refusal() -> None:
    """FIXTURE_MAILBOX_BACKEND=none → load_mailbox_backend returns
    None (target doesn't email) → AUTH_FIXTURE_REQUIRED detail=
    mailbox_required_for_reset (codex P2)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["s@example.invalid"])), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "mailbox_required_for_reset"
