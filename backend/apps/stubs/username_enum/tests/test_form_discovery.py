"""Tests for stub 2.1's form-discovery chunk.

After the RoE gate passes, the runner fetches the target's base URL
and parses the HTML for `<form>` elements that look like login
candidates. When none are found, the runner emits
`AUTH_FIXTURE_REQUIRED` (per the spec — most likely an SPA or a
target whose login page isn't at `/`).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import get_registry
from apps.stubs._test_factories import seed_target_run
from apps.stubs.username_enum.runner import run
from apps.stubs.username_enum.tests._helpers import _mock_response, _program


@pytest.mark.django_db
def test_no_forms_emits_fixture_required() -> None:
    """Empty page / SPA shell → AUTH_FIXTURE_REQUIRED with reason
    `no_auth_form_found`. No subsequent submits fire."""
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug="2.1",
    )
    response = _mock_response(body="<html><body></body></html>")

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs._shared.auth.discovery.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = response
        run(scan_run, target_run)

    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["reason"] == "fixture_required"
    assert ev.data["detail"] == "no_auth_form_found"
    assert str(ev.subject_id) == str(target_run.id)


@pytest.mark.django_db
def test_login_form_discovered_emits_no_fixture_event() -> None:
    """A page with a login form proceeds past discovery — slice 02
    chunk 3 picks up here. For chunk 2, success = no FIXTURE_REQUIRED
    event."""
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug="2.1",
    )
    response = _mock_response(body=(
        "<html><body>"
        '<form method="POST" action="/login">'
        '<input name="email">'
        '<input name="password" type="password">'
        "</form></body></html>"
    ))

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs._shared.auth.discovery.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = response
        run(scan_run, target_run)

    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    ).exists()


@pytest.mark.django_db
def test_transport_error_emits_probe_refused() -> None:
    """httpx.RequestError (timeout, DNS, TLS) → AUTH_PROBE_REFUSED
    with reason `transport_error`. Not AUTH_FIXTURE_REQUIRED — a
    network failure isn't a fixture problem."""
    import httpx
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug="2.1",
    )

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs._shared.auth.discovery.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.ConnectError("no route to host")
        )
        run(scan_run, target_run)

    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["reason"] == "transport_error"
    assert ev.data["error"] == "ConnectError"
    # Verify it did NOT route to AUTH_FIXTURE_REQUIRED.
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    ).exists()


@pytest.mark.django_db
def test_cross_origin_redirect_refused() -> None:
    """A target that 301-redirects to an out-of-scope host (e.g. SSO
    provider) must emit OUT_OF_SCOPE_REJECTED and halt — without
    parsing forms from the off-scope page."""
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug="2.1",
    )
    # Same body content + form, but final URL is on a different host.
    response = _mock_response(body=(
        "<html><body>"
        '<form method="POST" action="/login">'
        '<input name="email">'
        '<input name="password" type="password">'
        "</form></body></html>"
    ))
    response.url = "https://login.evil.invalid/"

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs._shared.auth.discovery.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = response
        run(scan_run, target_run)

    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
    ).exists()
    # And NO fixture-required event — the cross-origin refusal is the
    # primary signal.
    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    ).exists()
