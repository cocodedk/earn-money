"""End-to-end tests for stub 2.20 (email-verification-bypass)."""
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
from apps.stubs.email_verification_bypass.runner import run


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


def _resp(*, status: int, body: str = "", headers: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.headers = headers or {}
    return r


@pytest.mark.django_db
def test_register_201_login_with_token_emits_finding() -> None:
    """Juice-Shop-style: registration 201, login 200 with JWT token →
    Finding(category=auth_email_verification_bypass, MEDIUM, candidate,
    confidence=medium since registration didn't say verify_required)."""
    reg = _resp(status=201, body='{"data":{"id":42,"email":"x"}}')
    login = _resp(
        status=200,
        body='{"authentication":{"token":"eyJhbGc..."}}',
        headers={"Content-Type": "application/json"},  # non-cookie header
    )
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=reg), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api",
               return_value=login):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_email_verification_bypass"
    assert f.severity == "medium"
    assert f.confidence == "medium"  # no verify_required signal
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["login_status"] == 200
    assert f.data["registration_required_verification"] is False
    assert f.data["requires_manual_review"] is True
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_verify_required_text_upgrades_confidence_to_high() -> None:
    """Registration body says 'check your inbox' AND login still
    succeeds → confidence=high (system intended verification, failed
    to enforce it)."""
    reg = _resp(
        status=201,
        body='{"message":"Account created. Please check your inbox to verify."}',
    )
    login = _resp(
        status=200, headers={"Set-Cookie": "sid=abc"},
    )
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=reg), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api",
               return_value=login):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.confidence == "high"
    assert f.data["registration_required_verification"] is True


@pytest.mark.django_db
def test_json_emailverified_false_upgrades_confidence() -> None:
    """Registration JSON body `emailVerified:false` (compact) and
    login succeeds → confidence=high via the JSON-marker substring
    set."""
    reg = _resp(
        status=201,
        body='{"data":{"id":7,"emailVerified":false}}',
    )
    login = _resp(status=200, headers={"Set-Cookie": "sid=x"})
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=reg), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api",
               return_value=login):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.confidence == "high"


@pytest.mark.django_db
def test_login_blocked_no_finding() -> None:
    """Registration succeeds, login 401 (email not verified) → no
    Finding (target IS enforcing verification)."""
    reg = _resp(status=201, body='{"data":{"id":42}}')
    login = _resp(status=401, body='{"error":"email not verified"}')
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=reg), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api",
               return_value=login):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_login_2xx_but_no_session_evidence_no_finding() -> None:
    """Login 200 but no Set-Cookie and no token-like body marker →
    treated as not-actually-authenticated (e.g., welcome page after
    submitting bad creds). No Finding."""
    reg = _resp(status=201, body='{"data":{"id":42}}')
    login = _resp(status=200, body="Welcome guest. Please verify your email.")
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=reg), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api",
               return_value=login):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_login_transport_failure_no_finding() -> None:
    """Login transport-fails (None) → no Finding."""
    reg = _resp(status=201, body='{"data":{"id":42}}')
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=reg), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api",
               return_value=None):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_non_json_registration_body_no_crash() -> None:
    """Registration response with non-JSON body (e.g., HTML page) →
    substring scan finds no marker, confidence stays medium."""
    reg = _resp(status=201, body="<html><body>welcome</body></html>")
    login = _resp(status=200, headers={"Set-Cookie": "sid=x"})
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.20")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.email_verification_bypass.runner.register_via_api",
               return_value=reg), \
         patch("apps.stubs.email_verification_bypass.runner.login_via_api",
               return_value=login):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.confidence == "medium"
