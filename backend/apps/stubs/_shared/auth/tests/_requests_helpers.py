"""Shared `_form()` fixture-builder for test_requests*.py modules.

Underscore prefix marks this as test-only. Not imported by production
code.
"""
from __future__ import annotations

from apps.stubs._shared.auth.forms import AuthForm


def make_form(
    method: str = "POST",
    action: str = "https://x.test/login",
) -> AuthForm:
    return AuthForm(
        method=method,  # type: ignore[arg-type]
        action_url=action,
        content_type="application/x-www-form-urlencoded",
        identifier_field="email",
        password_field="password",
        hidden_fields={"csrf": "tok-A"},
        flow_hint="login",
    )
