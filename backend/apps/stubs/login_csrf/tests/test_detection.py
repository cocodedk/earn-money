"""End-to-end tests for stub 2.18 (login-csrf)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.discovery import FetchOutcome
from apps.stubs._test_factories import seed_target_run
from apps.stubs.login_csrf.runner import run


def _program() -> Program:
    return Program(
        platform="local", slug="dvwa",
        scope=Scope(
            platform="local", slug="dvwa",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=10),
    )


def _outcome(body: str) -> FetchOutcome:
    return FetchOutcome(
        ok=True, status=200, body=body, content_type="text/html",
        final_url="https://x.example/", error=None,
    )


@pytest.mark.django_db
def test_login_form_without_csrf_emits_finding() -> None:
    """Login form has only username + password (no anti-CSRF hidden
    field) → Finding(MEDIUM, auth_login_csrf, candidate)."""
    body = (
        "<html><body>"
        "<form action='/login' method='POST'>"
        "<input type='text' name='username'>"
        "<input type='password' name='password'>"
        "</form></body></html>"
    )
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.18")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.login_csrf.runner.fetch_for_discovery",
               return_value=_outcome(body)):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_login_csrf"
    assert f.severity == "medium"
    assert f.confidence == "medium"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["indicator"] == "missing_form_csrf_token"
    assert f.data["requires_manual_review"] is True
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_login_form_with_csrf_token_no_finding() -> None:
    """Standard `csrf_token` hidden field present → no Finding."""
    body = (
        "<html><body>"
        "<form action='/login' method='POST'>"
        "<input type='text' name='username'>"
        "<input type='password' name='password'>"
        "<input type='hidden' name='csrf_token' value='abc123'>"
        "</form></body></html>"
    )
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.18")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.login_csrf.runner.fetch_for_discovery",
               return_value=_outcome(body)):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_dvwa_user_token_field_no_finding() -> None:
    """DVWA-style `user_token` hidden field → no Finding."""
    body = (
        "<html><body>"
        "<form action='/login.php' method='POST'>"
        "<input type='text' name='username'>"
        "<input type='password' name='password'>"
        "<input type='hidden' name='user_token' value='deadbeef'>"
        "</form></body></html>"
    )
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.18")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.login_csrf.runner.fetch_for_discovery",
               return_value=_outcome(body)):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_case_insensitive_csrf_name_match() -> None:
    """`__RequestVerificationToken` (ASP.NET style) → no Finding."""
    body = (
        "<html><body>"
        "<form action='/login' method='POST'>"
        "<input type='text' name='username'>"
        "<input type='password' name='password'>"
        "<input type='hidden' name='__RequestVerificationToken' value='x'>"
        "</form></body></html>"
    )
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.18")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.login_csrf.runner.fetch_for_discovery",
               return_value=_outcome(body)):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_unrelated_hidden_field_does_not_protect() -> None:
    """Hidden field with non-CSRF name (e.g. `return_to`) → Finding
    fires (those don't protect against CSRF)."""
    body = (
        "<html><body>"
        "<form action='/login' method='POST'>"
        "<input type='text' name='username'>"
        "<input type='password' name='password'>"
        "<input type='hidden' name='return_to' value='/home'>"
        "</form></body></html>"
    )
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.18")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.login_csrf.runner.fetch_for_discovery",
               return_value=_outcome(body)):
        run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run).count() == 1
