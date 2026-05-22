"""Unit tests for `reset_poisoning.submit.request_reset_with_host_header`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from apps.stubs._shared.auth.forms import AuthForm
from apps.stubs.reset_poisoning.submit import request_reset_with_host_header


def _form() -> AuthForm:
    return AuthForm(
        method="POST",
        action_url="https://x.example/forgot-password",
        content_type="application/x-www-form-urlencoded",
        identifier_field="email", password_field=None,
        hidden_fields={"csrf": "tok"}, flow_hint="password_reset",
    )


def _patch(response=None, error=None):
    """Patch Client so client.request(...) returns response or raises."""
    class _FakeClient:
        def __init__(self, **_kw): pass
        def __enter__(self): return self
        def __exit__(self, *_a): return None
        def request(self, method, url, **kw):  # type: ignore[no-untyped-def]
            if error is not None:
                raise error
            return response
    return patch("apps.stubs.reset_poisoning.submit.Client", _FakeClient)


def test_2xx_returns_true() -> None:
    with _patch(response=MagicMock(status_code=200)):
        ok = request_reset_with_host_header(
            form=_form(), identifier_value="s@x.invalid",
            x_forwarded_host="evil.invalid", user_agent="scan",
        )
    assert ok is True


def test_3xx_returns_true() -> None:
    with _patch(response=MagicMock(status_code=302)):
        ok = request_reset_with_host_header(
            form=_form(), identifier_value="s@x.invalid",
            x_forwarded_host="evil.invalid", user_agent="scan",
        )
    assert ok is True


def test_4xx_returns_false() -> None:
    with _patch(response=MagicMock(status_code=400)):
        ok = request_reset_with_host_header(
            form=_form(), identifier_value="s@x.invalid",
            x_forwarded_host="evil.invalid", user_agent="scan",
        )
    assert ok is False


def test_transport_error_returns_false() -> None:
    with _patch(error=httpx.ConnectError("boom")):
        ok = request_reset_with_host_header(
            form=_form(), identifier_value="s@x.invalid",
            x_forwarded_host="evil.invalid", user_agent="scan",
        )
    assert ok is False


def test_x_forwarded_host_header_injected() -> None:
    """The host header value passed in must end up in the outbound
    request's `x-forwarded-host` header."""
    captured: dict = {}

    class _FakeClient:
        def __init__(self, **_kw): pass
        def __enter__(self): return self
        def __exit__(self, *_a): return None
        def request(self, method, url, *, data, headers):  # type: ignore[no-untyped-def]
            captured["headers"] = headers
            return MagicMock(status_code=200)

    with patch("apps.stubs.reset_poisoning.submit.Client", _FakeClient):
        request_reset_with_host_header(
            form=_form(), identifier_value="s@x.invalid",
            x_forwarded_host="poison.example.invalid",
            user_agent="scanner",
        )
    assert captured["headers"]["x-forwarded-host"] == "poison.example.invalid"
    assert captured["headers"]["user-agent"] == "scanner"


def test_form_without_identifier_field_skips_payload_field() -> None:
    """An AuthForm with `identifier_field=None` still posts the
    hidden fields without injecting the identifier."""
    captured: dict = {}

    class _FakeClient:
        def __init__(self, **_kw): pass
        def __enter__(self): return self
        def __exit__(self, *_a): return None
        def request(self, method, url, *, data, headers):  # type: ignore[no-untyped-def]
            captured["data"] = data
            return MagicMock(status_code=200)

    form = AuthForm(
        method="POST", action_url="https://x.example/forgot",
        content_type="application/x-www-form-urlencoded",
        identifier_field=None, password_field=None,
        hidden_fields={"csrf": "t"}, flow_hint="password_reset",
    )
    with patch("apps.stubs.reset_poisoning.submit.Client", _FakeClient):
        request_reset_with_host_header(
            form=form, identifier_value="ignored",
            x_forwarded_host="evil.invalid", user_agent="s",
        )
    assert captured["data"] == {"csrf": "t"}
