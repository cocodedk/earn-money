"""Contract tests for `_shared/auth/forms.discover_forms` + helpers.

Covers the spec 2.1 §1 auth-form detection signals: password input,
identifier-named input, JSON endpoint route, page title/form action
keywords. Plus flow-hint inference + CSRF hidden-field capture.
"""
from __future__ import annotations

import pytest

from apps.stubs._shared.auth.forms import (
    AuthForm, discover_forms, discover_json_endpoints,
)


BASE = "https://example.invalid"


def _form(html_inner: str) -> str:
    return f"<!doctype html><html><body>{html_inner}</body></html>"


# ----- HTML password-input forms ------------------------------------

def test_login_form_with_password_input_discovered() -> None:
    html = _form(
        '<form method="POST" action="/login">'
        '<input name="email" type="email">'
        '<input name="password" type="password">'
        '<button type="submit">Sign in</button>'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    assert len(forms) == 1
    f = forms[0]
    assert f.method == "POST"
    assert f.action_url == f"{BASE}/login"
    assert f.identifier_field == "email"
    assert f.password_field == "password"
    assert f.flow_hint == "login"


def test_username_field_preferred_over_other_identifier_names() -> None:
    """When multiple identifier candidates exist, prefer email then
    username — most stubs target those names first."""
    html = _form(
        '<form method="POST" action="/auth/login">'
        '<input name="account">'
        '<input name="username">'
        '<input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    assert forms[0].identifier_field == "username"


def test_email_input_preferred_over_username() -> None:
    html = _form(
        '<form method="POST" action="/login">'
        '<input name="username">'
        '<input name="email">'
        '<input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    assert forms[0].identifier_field == "email"


def test_reset_form_no_password_field() -> None:
    """A form with only an identifier (no password) on a reset-themed
    action URL parses as password_reset with password_field=None."""
    html = _form(
        '<form method="POST" action="/password-reset">'
        '<input name="email" type="email">'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    assert len(forms) == 1
    assert forms[0].password_field is None
    assert forms[0].flow_hint == "password_reset"


def test_registration_form_flow_hint() -> None:
    html = _form(
        '<form method="POST" action="/signup">'
        '<input name="email">'
        '<input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    assert forms[0].flow_hint == "registration"


def test_oauth_callback_form_flow_hint() -> None:
    html = _form(
        '<form method="POST" action="/oauth/callback">'
        '<input name="code"><input name="state">'
        '</form>'
    )
    # No identifier field at all → not an auth-candidate form.
    assert discover_forms(html, BASE) == []


def test_unknown_flow_hint_when_action_url_neutral() -> None:
    html = _form(
        '<form method="POST" action="/api/v1/foo">'
        '<input name="login"><input name="password" type="password">'
        '</form>'
    )
    assert discover_forms(html, BASE)[0].flow_hint == "unknown"


# ----- CSRF + hidden fields -----------------------------------------

def test_csrf_hidden_inputs_captured() -> None:
    html = _form(
        '<form method="POST" action="/login">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="abc123">'
        '<input type="hidden" name="next" value="/dashboard">'
        '<input name="email"><input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    hidden = forms[0].hidden_fields
    assert hidden["csrfmiddlewaretoken"] == "abc123"
    assert hidden["next"] == "/dashboard"


# ----- multiple forms on one page -----------------------------------

def test_multiple_forms_all_returned() -> None:
    html = _form(
        '<form method="POST" action="/login">'
        '<input name="email"><input name="password" type="password">'
        '</form>'
        '<form method="POST" action="/signup">'
        '<input name="email"><input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    assert len(forms) == 2
    assert {f.flow_hint for f in forms} == {"login", "registration"}


def test_form_action_resolved_to_absolute_url() -> None:
    html = _form(
        '<form method="POST" action="login">'
        '<input name="email"><input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, "https://example.invalid/account/")
    assert forms[0].action_url == "https://example.invalid/account/login"


def test_form_without_action_uses_base_url() -> None:
    """A form with no action attribute submits to the same URL the
    page was served from — the spec's same-origin semantics."""
    html = _form(
        '<form method="POST">'
        '<input name="email"><input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, "https://example.invalid/login")
    assert forms[0].action_url == "https://example.invalid/login"


# ----- GET credential forms still discovered (refusal happens later) ---

def test_password_only_form_is_discovered() -> None:
    """Spec 2.1 §1: a form with a password field BUT NO identifier-named
    input is still an auth candidate (PIN entry, sudo-confirm, second
    step of multi-page login). Discovery is permissive; the runner
    decides whether its specific stub can use this candidate."""
    html = _form(
        '<form method="POST" action="/confirm-password">'
        '<input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    assert len(forms) == 1
    assert forms[0].password_field == "password"
    assert forms[0].identifier_field is None


def test_get_credential_form_is_discovered_for_safety_layer_to_refuse() -> None:
    """Per spec 2.1 §2.6 — `GET` forms with password inputs are
    refused by the safety layer downstream; discovery itself stays
    passive so the runner sees them."""
    html = _form(
        '<form method="GET" action="/login">'
        '<input name="email"><input name="password" type="password">'
        '</form>'
    )
    forms = discover_forms(html, BASE)
    assert len(forms) == 1
    assert forms[0].method == "GET"


# ----- non-auth content ignored -------------------------------------

def test_empty_body_returns_empty_list() -> None:
    assert discover_forms("", BASE) == []


def test_no_form_returns_empty_list() -> None:
    assert discover_forms("<html><body><p>hi</p></body></html>", BASE) == []


def test_form_without_password_or_identifier_input_ignored() -> None:
    """A `<form>` that contains only a search box or comment field is
    not an auth candidate."""
    html = _form(
        '<form method="POST" action="/search">'
        '<input name="q"><button>go</button>'
        '</form>'
    )
    assert discover_forms(html, BASE) == []


def test_non_html_content_type_returns_empty() -> None:
    """JSON / binary content-types skip the HTML parser entirely."""
    assert discover_forms(
        '{"login": "/api/auth"}', BASE,
        response_content_type="application/json",
    ) == []


# ----- JSON-endpoint discovery --------------------------------------

def test_json_endpoint_with_login_route_discovered() -> None:
    body = (
        b'{"routes": [{"path": "/api/v1/login", "method": "POST"}]}'
    )
    forms = discover_json_endpoints(
        body, BASE, response_content_type="application/json",
    )
    assert any(f.flow_hint == "login" for f in forms)
    assert all(f.content_type == "application/json" for f in forms)


def test_json_endpoint_non_json_content_type_returns_empty() -> None:
    assert discover_json_endpoints(
        b'{"routes": []}', BASE,
        response_content_type="text/html",
    ) == []


def test_json_endpoint_unparseable_body_returns_empty() -> None:
    assert discover_json_endpoints(
        b'not json{', BASE,
        response_content_type="application/json",
    ) == []


def test_json_endpoint_empty_routes_returns_empty() -> None:
    assert discover_json_endpoints(
        b'{"routes": []}', BASE,
        response_content_type="application/json",
    ) == []


# ----- AuthForm immutability ----------------------------------------

def test_authform_is_frozen() -> None:
    """Mutating hidden_fields on a returned AuthForm must not be possible
    via attribute assignment."""
    html = _form(
        '<form method="POST" action="/login">'
        '<input name="email"><input name="password" type="password">'
        '</form>'
    )
    form = discover_forms(html, BASE)[0]
    with pytest.raises(Exception):
        form.method = "GET"  # type: ignore[misc]
