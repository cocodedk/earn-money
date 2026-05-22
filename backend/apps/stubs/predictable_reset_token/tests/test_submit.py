"""Tests for stub 2.5's reset-request submit module.

request_reset fires one password-reset POST and returns True on
2xx/3xx, False on 4xx/5xx or transport error. These tests cover
lines 23-41 of submit.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.stubs._shared.auth.forms import AuthForm
from apps.stubs.predictable_reset_token.submit import request_reset


def _form(
    *,
    identifier_field: str | None = "email",
    hidden: dict | None = None,
) -> AuthForm:
    return AuthForm(
        method="POST",
        action_url="https://x.example/password-reset",
        content_type="application/x-www-form-urlencoded",
        identifier_field=identifier_field,
        password_field=None,
        hidden_fields=hidden or {},
        flow_hint="password_reset",
    )


def _mock_resp(*, status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


def test_request_reset_returns_true_on_200() -> None:
    with patch(
        "apps.stubs.predictable_reset_token.submit.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.request.return_value = (
            _mock_resp(status=200)
        )
        assert request_reset(
            form=_form(), identifier_value="user@example.invalid"
        ) is True


def test_request_reset_returns_true_on_302() -> None:
    with patch(
        "apps.stubs.predictable_reset_token.submit.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.request.return_value = (
            _mock_resp(status=302)
        )
        assert request_reset(
            form=_form(), identifier_value="user@example.invalid"
        ) is True


def test_request_reset_returns_false_on_400() -> None:
    with patch(
        "apps.stubs.predictable_reset_token.submit.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.request.return_value = (
            _mock_resp(status=400)
        )
        assert request_reset(
            form=_form(), identifier_value="user@example.invalid"
        ) is False


def test_request_reset_returns_false_on_transport_error() -> None:
    import httpx
    with patch(
        "apps.stubs.predictable_reset_token.submit.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.request.side_effect = (
            httpx.ConnectError("refused")
        )
        assert request_reset(
            form=_form(), identifier_value="user@example.invalid"
        ) is False


def test_request_reset_omits_identifier_when_field_is_none() -> None:
    """A form with no identifier_field (password-only) should still
    succeed — the identifier param is simply omitted from the payload."""
    captured: list = []

    def _fake_request(method, url, *, data, headers):
        captured.append(data)
        return _mock_resp(status=200)

    with patch(
        "apps.stubs.predictable_reset_token.submit.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.request.side_effect = (
            _fake_request
        )
        result = request_reset(
            form=_form(identifier_field=None),
            identifier_value="user@example.invalid",
        )
    assert result is True
    # No identifier key in payload
    assert "email" not in captured[0]


def test_request_reset_includes_hidden_fields() -> None:
    """Hidden fields from the form (CSRF etc.) are merged into payload."""
    captured: list = []

    def _fake_request(method, url, *, data, headers):
        captured.append(data)
        return _mock_resp(status=200)

    with patch(
        "apps.stubs.predictable_reset_token.submit.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.request.side_effect = (
            _fake_request
        )
        request_reset(
            form=_form(hidden={"csrfmiddlewaretoken": "tok123"}),
            identifier_value="user@example.invalid",
        )
    assert captured[0].get("csrfmiddlewaretoken") == "tok123"
