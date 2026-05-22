"""Shared helpers for predictable_reset_token tests."""
from __future__ import annotations

from unittest.mock import MagicMock

from apps.programs.loader import Program
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.forms import AuthForm


def _program(
    *,
    active_login: bool = False,
    reset_probes: bool = True,
    accounts: list[str] | None = None,
) -> Program:
    if accounts is None:
        accounts = ["scanner@example.invalid"]
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_active_login_probes=active_login,
            allow_password_reset_probes=reset_probes,
            authorized_test_accounts=accounts,
        ),
    )


RESET_FORM = AuthForm(
    method="POST",
    action_url="https://x.example/password-reset",
    content_type="application/x-www-form-urlencoded",
    identifier_field="email",
    password_field=None,
    hidden_fields={},
    flow_hint="password_reset",
)


class _DrainingMailbox:
    """Pops messages one-at-a-time; returns None when exhausted."""

    def __init__(self, messages):
        self._messages = list(messages)

    def wait_for_message(self, addr, *, since, timeout_s=30.0):
        return self._messages.pop(0) if self._messages else None


def _mock_response(
    *,
    body: str,
    url: str = "https://x.example/",
    content_type: str = "text/html",
) -> MagicMock:
    r = MagicMock()
    r.text = body
    r.url = url
    r.headers = {"content-type": content_type}
    return r
