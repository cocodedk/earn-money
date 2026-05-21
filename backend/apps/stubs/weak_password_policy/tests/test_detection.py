"""End-to-end tests for stub 2.2 (weak-password-policy)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.weak_password_policy.runner import run


def _program() -> Program:
    return Program(
        platform="local", slug="juice-shop",
        scope=Scope(
            platform="local", slug="juice-shop",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_registration_probes=True,
        ),
    )


def _resp(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


@pytest.mark.django_db
def test_first_candidate_accepted_emits_finding() -> None:
    """Juice-Shop-style: register endpoint returns 201 for the FIRST
    candidate (too-short) → Finding(MEDIUM, auth_weak_password_policy)
    with accepted_class=too_short. No further candidates tried."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_password_policy.runner.register_via_api",
               side_effect=[_resp(201), _resp(201), _resp(201)]) as mock_reg:
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_weak_password_policy"
    assert f.severity == "medium"
    assert f.confidence == "high"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["accepted_class"] == "too_short"
    assert f.data["accepted_status"] == 201
    assert mock_reg.call_count == 1  # stopped after first accept
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_third_candidate_accepted_after_400s() -> None:
    """Server rejects the first two (400), accepts the third (numeric-
    only) → Finding with accepted_class=numeric_only."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_password_policy.runner.register_via_api",
               side_effect=[_resp(400), _resp(400), _resp(201)]) as mock_reg:
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.data["accepted_class"] == "numeric_only"
    assert mock_reg.call_count == 3


@pytest.mark.django_db
def test_no_candidate_accepted_no_finding() -> None:
    """Hardened target rejects all three weak candidates → no
    Finding emitted, no transport_error refusal (responses were
    seen)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_password_policy.runner.register_via_api",
               side_effect=[_resp(400), _resp(400), _resp(400)]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_partial_transport_errors_then_acceptance() -> None:
    """First two candidates produce transport errors (None), third
    yields 201 → Finding emitted for the third class."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.2")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_password_policy.runner.register_via_api",
               side_effect=[None, None, _resp(201)]):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.data["accepted_class"] == "numeric_only"
