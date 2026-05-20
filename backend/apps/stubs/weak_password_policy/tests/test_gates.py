"""Tests for stub 2.2's RoE + fixture gates.

The full submit-progressively-weaker-passwords chain depends on a
provisioned canary account; until that lands, the stub's contract is
"refuse with the right AUTH_* event so the operator sees what to
provision".
"""
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


def _program(
    *,
    login_probes: bool = True,
    accounts: list[str] | None = None,
) -> Program:
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_active_login_probes=login_probes,
            authorized_test_accounts=accounts or [],
        ),
    )


@pytest.mark.django_db
def test_roe_disabled_emits_probe_refused() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(login_probes=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["reason"] == "roe_disabled"


@pytest.mark.django_db
def test_no_authorized_test_account_emits_fixture_required() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=[])):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["reason"] == "fixture_required"
    assert ev.data["detail"] == "no_authorized_test_accounts"


@pytest.mark.django_db
def test_missing_fixture_password_secret_emits_fixture_required(monkeypatch) -> None:
    """Account is authorised but FIXTURE_TEST_PASSWORD env var is unset
    → AUTH_FIXTURE_REQUIRED with reason=`missing_fixture_secret` +
    data.missing_secret naming the env var the operator must set."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    monkeypatch.delenv("FIXTURE_TEST_PASSWORD", raising=False)

    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["scanner@example.invalid"])):
        run(scan_run, target_run)

    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["reason"] == "missing_fixture_secret"
    assert ev.data["missing_secret"] == "FIXTURE_TEST_PASSWORD"


@pytest.mark.django_db
def test_all_gates_pass_returns_silently(monkeypatch) -> None:
    """All gates satisfied — runner returns without emitting any
    refusal event. (The detection chain lands in a later commit when
    fixture provisioning is wired up.)"""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    monkeypatch.setenv("FIXTURE_TEST_PASSWORD", "canary-correct-horse")

    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["scanner@example.invalid"])):
        run(scan_run, target_run)

    assert not Event.objects.filter(
        scan_run=scan_run,
        type__in=[
            EventType.AUTH_PROBE_REFUSED,
            EventType.AUTH_FIXTURE_REQUIRED,
        ],
    ).exists()
