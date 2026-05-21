"""Unit tests for `_shared/auth/forms.pick_login_form`."""
from __future__ import annotations

from apps.stubs._shared.auth.forms import AuthForm, pick_login_form


def _form(
    *, flow_hint: str = "login", password_field: str | None = "password",
    action_url: str = "https://x.example/login",
) -> AuthForm:
    return AuthForm(
        method="POST", action_url=action_url,
        content_type="application/x-www-form-urlencoded",
        identifier_field="username", password_field=password_field,
        hidden_fields={}, flow_hint=flow_hint,  # type: ignore[arg-type]
    )


def test_empty_list_returns_none() -> None:
    assert pick_login_form([]) is None


def test_first_login_with_password_field_returned() -> None:
    login = _form()
    assert pick_login_form([login]) is login


def test_login_without_password_field_skipped() -> None:
    """A login form with no password input cannot host a credential
    probe — pick_login_form skips it."""
    assert pick_login_form([_form(password_field=None)]) is None


def test_non_login_form_skipped() -> None:
    reset = _form(flow_hint="password_reset")
    assert pick_login_form([reset]) is None


def test_first_qualifying_form_wins() -> None:
    """Two login forms with password fields → the first one returned."""
    a = _form(action_url="https://x.example/a")
    b = _form(action_url="https://x.example/b")
    assert pick_login_form([a, b]) is a


def test_non_login_precedes_login_picks_login() -> None:
    reset = _form(flow_hint="password_reset")
    login = _form()
    assert pick_login_form([reset, login]) is login
