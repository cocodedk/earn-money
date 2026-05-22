"""Gate tests for stub 2.21 (invitation-abuse)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.invitation_abuse.runner import run


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
            allow_registration_probes=knob_on,
            authorized_test_accounts=accounts or [],
        ),
    )


@pytest.mark.django_db
def test_roe_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.21")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(knob_on=False)):
        run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_no_authorized_accounts() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.21")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=[])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_authorized_test_accounts"


@pytest.mark.django_db
def test_missing_secret(monkeypatch) -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.21")
    monkeypatch.delenv("FIXTURE_INVITATION_TOKEN", raising=False)
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["scanner@example.invalid"])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["missing_secret"] == "FIXTURE_INVITATION_TOKEN"


def _noop_client() -> MagicMock:
    client = MagicMock()
    login = MagicMock()
    login.status_code = 200
    login.json.return_value = {"token": "tok", "userId": "scanner"}
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.post.return_value = login
    return client


@pytest.mark.django_db
def test_all_gates_pass(monkeypatch) -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.21")
    monkeypatch.setenv("FIXTURE_INVITATION_TOKEN", "fixture-value")
    noop_resp = MagicMock()
    noop_resp.status_code = 404
    noop_resp.text = "{}"
    noop_resp.request = MagicMock()
    noop_resp.request.method = "GET"
    _mod = "apps.stubs.invitation_abuse.runner"
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["scanner@example.invalid"])):
        with patch(f"{_mod}.httpx.Client", return_value=_noop_client()):
            with patch(f"{_mod}.submit_probe", return_value=noop_resp):
                run(scan_run, target_run)
    assert not Event.objects.filter(
        scan_run=scan_run,
        type__in=[EventType.AUTH_PROBE_REFUSED, EventType.AUTH_FIXTURE_REQUIRED],
    ).exists()
