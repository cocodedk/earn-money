"""End-to-end tests for stub 2.21 (invitation-abuse) runner."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.invitation_abuse.runner import run

_MODULE = "apps.stubs.invitation_abuse.runner"


def _program(*, knob_on: bool = True, accounts: list[str] | None = None) -> Program:
    return Program(
        platform="local", slug="invitation-abuse-lab",
        scope=Scope(
            platform="local", slug="invitation-abuse-lab",
            policy="rate-limited-OK",
            in_scope=["invitation-abuse-lab"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_registration_probes=knob_on,
            authorized_test_accounts=accounts or ["inviter"],
        ),
    )


def _login_client(ok: bool = True) -> MagicMock:
    client = MagicMock()
    login = MagicMock()
    login.status_code = 200 if ok else 401
    login.json.return_value = {"token": "tok-inviter", "userId": "inviter"}
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.post.return_value = login
    return client


def _preview_resp() -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.request = MagicMock()
    r.request.method = "GET"
    r.text = '{"workspace":"acme-test","role":"member","invited_by":"i@example.test"}'
    r.headers = {}
    return r


def _safe_resp() -> MagicMock:
    r = MagicMock()
    r.status_code = 404
    r.request = MagicMock()
    r.request.method = "GET"
    r.text = '{"error":"not_found"}'
    r.headers = {}
    return r


def _wrong_recipient_resp() -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.request = MagicMock()
    r.request.method = "POST"
    r.text = '{"status":"accepted","member_created":true}'
    r.headers = {}
    return r


@pytest.mark.django_db
def test_preview_exposure_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_INVITATION_TOKEN", "fixture-invite-token-001")
    monkeypatch.setenv("FIXTURE_INVITE_LAB_URL", "http://invitation-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="invitation-abuse-lab", stub_slug="2.21")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", return_value=_preview_resp()):
                run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.21").exists()


@pytest.mark.django_db
def test_no_preview_exposure_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_INVITATION_TOKEN", "fixture-invite-token-001")
    monkeypatch.setenv("FIXTURE_INVITE_LAB_URL", "http://invitation-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="invitation-abuse-lab", stub_slug="2.21")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", return_value=_safe_resp()):
                run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.21").exists()


@pytest.mark.django_db
def test_wrong_recipient_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_INVITATION_TOKEN", "fixture-invite-token-001")
    monkeypatch.setenv("FIXTURE_INVITE_LAB_URL", "http://invitation-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="invitation-abuse-lab", stub_slug="2.21")

    safe = _safe_resp()
    accept = _wrong_recipient_resp()
    responses = iter([safe, safe, accept])

    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", side_effect=lambda _r: next(responses)):
                run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.21").exists()


@pytest.mark.django_db
def test_login_failure_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_INVITATION_TOKEN", "fixture-invite-token-001")
    monkeypatch.setenv("FIXTURE_INVITE_LAB_URL", "http://invitation-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="invitation-abuse-lab", stub_slug="2.21")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client(ok=False)):
            run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_transport_error_on_surface_probe_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_INVITATION_TOKEN", "fixture-invite-token-001")
    monkeypatch.setenv("FIXTURE_INVITE_LAB_URL", "http://invitation-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="invitation-abuse-lab", stub_slug="2.21")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", return_value=None):
                run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_transport_error_on_preview_probe_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_INVITATION_TOKEN", "fixture-invite-token-001")
    monkeypatch.setenv("FIXTURE_INVITE_LAB_URL", "http://invitation-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="invitation-abuse-lab", stub_slug="2.21")
    surface_ok = _safe_resp()
    responses = iter([surface_ok, None])
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", side_effect=lambda _r: next(responses)):
                run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_transport_error_on_accept_probe_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_INVITATION_TOKEN", "fixture-invite-token-001")
    monkeypatch.setenv("FIXTURE_INVITE_LAB_URL", "http://invitation-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="invitation-abuse-lab", stub_slug="2.21")
    surface_ok = _safe_resp()
    preview_ok = _safe_resp()
    responses = iter([surface_ok, preview_ok, None])
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", side_effect=lambda _r: next(responses)):
                run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
