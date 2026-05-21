"""Gate tests for stub 2.16 (oauth-token-substitution)."""
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
from apps.stubs.oauth_token_substitution.runner import run

_MODULE = "apps.stubs.oauth_token_substitution.runner"


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
            allow_oauth_probes=knob_on,
            authorized_test_accounts=accounts or [],
        ),
    )


@pytest.mark.django_db
def test_roe_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.16")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(knob_on=False)):
        run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_no_authorized_accounts() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.16")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=[])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_authorized_test_accounts"


@pytest.mark.django_db
def test_missing_secret(monkeypatch) -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.16")
    monkeypatch.delenv("FIXTURE_OAUTH_CLIENT_SECRET", raising=False)
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["scanner@example.invalid"])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["missing_secret"] == "FIXTURE_OAUTH_CLIENT_SECRET"


@pytest.mark.django_db
def test_all_gates_pass(monkeypatch) -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.16")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    _no_signals = FetchOutcome(
        ok=True, status=200, body="<html>Login</html>",
        content_type="text/html", final_url="http://x.example/login", error=None,
    )
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["scanner@example.invalid"])):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=_no_signals):
            run(scan_run, target_run)
    assert not Event.objects.filter(
        scan_run=scan_run,
        type__in=[EventType.AUTH_PROBE_REFUSED, EventType.AUTH_FIXTURE_REQUIRED],
    ).exists()
