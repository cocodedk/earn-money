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
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.username_enum.runner import run


def _program() -> Program:
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_active_login_probes=True,
        ),
    )


def _mock_httpx_get(*, body: str, status: int = 200, content_type: str = "text/html"):
    """Patch httpx.Client used inside username_enum.fetcher."""
    from unittest.mock import MagicMock
    response = MagicMock()
    response.status_code = status
    response.text = body
    response.headers = {"content-type": content_type}
    response.url = "https://x.example/"
    return response


@pytest.mark.django_db
def test_no_forms_emits_fixture_required() -> None:
    """Empty page / SPA shell → AUTH_FIXTURE_REQUIRED with reason
    `no_auth_form_found`. No subsequent submits fire."""
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug="2.1",
    )
    response = _mock_httpx_get(body="<html><body></body></html>")

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.username_enum.fetcher.httpx.Client") as client_cls:
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
    response = _mock_httpx_get(body=(
        "<html><body>"
        '<form method="POST" action="/login">'
        '<input name="email">'
        '<input name="password" type="password">'
        "</form></body></html>"
    ))

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.username_enum.fetcher.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = response
        run(scan_run, target_run)

    assert not Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    ).exists()


@pytest.mark.django_db
def test_transport_error_emits_fixture_required() -> None:
    """httpx.RequestError (timeout, DNS, TLS) → AUTH_FIXTURE_REQUIRED
    with reason `transport_error`. No further submits."""
    import httpx
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug="2.1",
    )

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.username_enum.fetcher.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.ConnectError("no route to host")
        )
        run(scan_run, target_run)

    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["detail"] == "transport_error"
