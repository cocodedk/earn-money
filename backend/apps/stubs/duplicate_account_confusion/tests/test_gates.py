"""Gate tests for stub 2.19 (duplicate-account-confusion)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.duplicate_account_confusion.runner import run


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
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.19")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(knob_on=False)):
        run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_no_authorized_accounts() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.19")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=[])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_authorized_test_accounts"


@pytest.mark.django_db
def test_missing_secret(monkeypatch) -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.19")
    monkeypatch.delenv("FIXTURE_TEST_PASSWORD", raising=False)
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["scanner@example.invalid"])):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["missing_secret"] == "FIXTURE_TEST_PASSWORD"


@pytest.mark.django_db
def test_all_gates_pass_proceeds_to_detection(monkeypatch) -> None:
    """All gates passing → runner proceeds to the detection chain
    (covered by test_detection.py). This test asserts only that the
    pre-flight refusal events DO NOT fire when env + RoE + accounts
    are all in place."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.19")
    monkeypatch.setenv("FIXTURE_TEST_PASSWORD", "fixture-value")
    # Mock register_via_api to short-circuit the detection chain
    # (which would otherwise try real HTTP and fall back to a
    # transport-error refusal).
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=["scanner@example.invalid"])), \
         patch("apps.stubs.duplicate_account_confusion.runner.register_via_api",
               return_value=None):
        run(scan_run, target_run)
    # Transport-error refusal fires from the detection chain — that's
    # expected, not a gate failure. The gate-specific refusals don't fire.
    assert not Event.objects.filter(
        scan_run=scan_run,
        type=EventType.AUTH_PROBE_REFUSED,
        data__reason="roe_disabled",
    ).exists()
    assert not Event.objects.filter(
        scan_run=scan_run,
        type=EventType.AUTH_FIXTURE_REQUIRED,
    ).exists()
