"""End-to-end tests for stub 2.19 duplicate-account-confusion."""
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
from apps.stubs.duplicate_account_confusion.runner import run


def _program() -> Program:
    return Program(
        platform="local", slug="juice-shop",
        scope=Scope(
            platform="local", slug="juice-shop",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_registration_probes=True,
            authorized_test_accounts=["existing@example.invalid"],
        ),
    )


def _resp(
    *, status: int = 200, body: str = "",
    content_type: str = "application/json",
    url: str = "https://x.example/api/Users",
) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.headers = {"content-type": content_type}
    r.url = url
    return r


@pytest.mark.django_db
def test_distinct_responses_emit_finding(monkeypatch) -> None:
    """Juice-Shop-style: 201 for new email, 400 for existing →
    Finding(category=auth_duplicate_account_confusion, severity=MEDIUM)."""
    monkeypatch.setenv("FIXTURE_TEST_PASSWORD", "throwaway")
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.19")
    new_resp = _resp(
        status=201, body='{"status":"success","data":{"id":42}}',
    )
    existing_resp = _resp(
        status=400,
        body='{"message":"Validation error","errors":[{"field":"email","message":"email must be unique"}]}',
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.duplicate_account_confusion.runner.register_via_api",
               side_effect=[new_resp, existing_resp]):
        run(scan_run, target_run)
    finding = Finding.objects.get(scan_run=scan_run)
    assert finding.category == "auth_duplicate_account_confusion"
    assert finding.severity == "medium"
    assert finding.status == FindingStatus.CANDIDATE
    assert finding.data["differentiators_count"] >= 1
    assert "status_code" in finding.data["differentiator_kinds"]
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_identical_responses_no_finding(monkeypatch) -> None:
    """Hardened target: same response shape for new and existing
    emails → no Finding."""
    monkeypatch.setenv("FIXTURE_TEST_PASSWORD", "throwaway")
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.19")
    canon = _resp(
        status=200, body='{"status":"check your email"}',
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.duplicate_account_confusion.runner.register_via_api",
               side_effect=[canon, canon]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_transport_error_emits_refusal(monkeypatch) -> None:
    """register_via_api returns None for all paths → AUTH_PROBE_REFUSED
    reason=transport_error."""
    monkeypatch.setenv("FIXTURE_TEST_PASSWORD", "throwaway")
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.19")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.duplicate_account_confusion.runner.register_via_api",
               return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["reason"] == "transport_error"
