"""Contract tests for `_shared/auth/safety` — enums, budgets, refusal recorder."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.types import EventType
from apps.stubs._shared.auth.safety import (
    AbortSignal,
    ProbeBudget,
    ProbeState,
    RefusalReason,
    record_refusal,
)


# ----- enum values ---------------------------------------------------

def test_refusal_reason_values() -> None:
    assert RefusalReason.ROE_DISABLED.value == "roe_disabled"
    assert RefusalReason.UNSAFE_METHOD.value == "unsafe_method"
    assert RefusalReason.FIXTURE_REQUIRED.value == "fixture_required"
    assert RefusalReason.MISSING_SECRET.value == "missing_fixture_secret"
    assert RefusalReason.BUDGET_EXHAUSTED.value == "budget_exhausted"


def test_abort_signal_values() -> None:
    assert AbortSignal.CAPTCHA.value == "captcha"
    assert AbortSignal.WAF.value == "waf"
    assert AbortSignal.LOCKOUT.value == "lockout"
    assert AbortSignal.RATE_LIMIT.value == "rate_limit"
    assert AbortSignal.MFA.value == "mfa"


# ----- ProbeBudget + ProbeState --------------------------------------

def test_probe_budget_frozen_and_typed() -> None:
    budget = ProbeBudget(
        stub_id="2.1", max_forms=2, max_submits=4,
        allow_repeat_confirmation=True,
    )
    assert budget.stub_id == "2.1"
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        budget.max_forms = 99  # type: ignore[misc]


def test_probe_state_starts_empty() -> None:
    s = ProbeState()
    assert s.forms_seen == 0
    assert s.submits_made == 0


def test_probe_state_can_count_up() -> None:
    s = ProbeState()
    s.record_form()
    s.record_form()
    s.record_submit()
    assert s.forms_seen == 2
    assert s.submits_made == 1


def test_state_within_budget_methods() -> None:
    budget = ProbeBudget(
        stub_id="2.1", max_forms=1, max_submits=2,
        allow_repeat_confirmation=False,
    )
    state = ProbeState()
    assert state.can_record_form(budget) is True
    state.record_form()
    assert state.can_record_form(budget) is False  # cap reached
    assert state.can_record_submit(budget) is True
    state.record_submit()
    state.record_submit()
    assert state.can_record_submit(budget) is False


# ----- record_refusal emits an event --------------------------------

@pytest.mark.django_db
def test_record_refusal_emits_auth_probe_refused() -> None:
    from apps.events.models import Event
    from apps.stubs._test_factories import seed_target_run

    scan_run, target_run = seed_target_run(stub_slug="2.1", host="x.example")

    record_refusal(
        scan_run=scan_run, target_run=target_run,
        stub_id="2.1", reason=RefusalReason.ROE_DISABLED,
        details={"knob": "allow_active_login_probes"},
    )

    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["stub"] == "2.1"
    assert ev.data["reason"] == "roe_disabled"
    assert ev.data["would_have_submitted"] is False
    assert ev.data["knob"] == "allow_active_login_probes"
    # Subject must be the target_run (per scans.tasks convention), so
    # the dashboard can link "scan-run → target → refusal" cleanly.
    assert str(ev.subject_id) == str(target_run.id)


@pytest.mark.django_db
def test_record_refusal_for_fixture_required_uses_fixture_event() -> None:
    """FIXTURE_REQUIRED maps to AUTH_FIXTURE_REQUIRED, not AUTH_PROBE_REFUSED.
    The dashboard differentiates these so the operator sees missing fixtures
    distinctly from RoE refusals."""
    from apps.events.models import Event
    from apps.stubs._test_factories import seed_target_run

    scan_run, target_run = seed_target_run(stub_slug="2.5", host="x.example")

    record_refusal(
        scan_run=scan_run, target_run=target_run,
        stub_id="2.5", reason=RefusalReason.FIXTURE_REQUIRED,
        details={"missing_secret": "FIXTURE_MAILBOX_TOKEN"},
    )

    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["reason"] == "fixture_required"
    assert ev.data["missing_secret"] == "FIXTURE_MAILBOX_TOKEN"


@pytest.mark.django_db
def test_record_refusal_for_missing_secret_uses_fixture_event() -> None:
    """MISSING_SECRET also routes to AUTH_FIXTURE_REQUIRED — same root cause
    from the dashboard's perspective."""
    from apps.events.models import Event
    from apps.stubs._test_factories import seed_target_run

    scan_run, target_run = seed_target_run(stub_slug="2.5", host="x.example")

    record_refusal(
        scan_run=scan_run, target_run=target_run,
        stub_id="2.5", reason=RefusalReason.MISSING_SECRET,
    )

    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    ).exists()
