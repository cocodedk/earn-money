"""Unit tests for `email_change_takeover.submit`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from apps.stubs._shared.auth.tests._post_paths_helpers import patch_client
from apps.stubs.email_change_takeover.submit import (
    bearer_token_from, change_email_unauthed_password,
)


_TARGET = "apps.stubs.email_change_takeover.submit.Client"


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


# ---- change_email_unauthed_password ---------------------------------

def test_returns_first_non_404_response() -> None:
    queue = [_ok(200), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = change_email_unauthed_password(
            base_url="https://x.example", bearer_token="tok",
            new_email="new@example.invalid",
        )
    assert resp is not None and resp.status_code == 200
    assert len(queue) == 1


def test_skips_404_then_returns_next() -> None:
    queue = [_ok(404), _ok(405), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = change_email_unauthed_password(
            base_url="https://x.example", bearer_token="tok",
            new_email="new@example.invalid",
        )
    assert resp is not None and resp.status_code == 200


def test_all_404_returns_last() -> None:
    queue = [_ok(404)] * 6
    with patch_client(_TARGET, queue):
        resp = change_email_unauthed_password(
            base_url="https://x.example", bearer_token="tok",
            new_email="new@example.invalid",
        )
    assert resp is not None and resp.status_code == 404


def test_all_transport_errors_returns_none() -> None:
    queue: list = [httpx.ConnectError("boom")] * 6
    with patch_client(_TARGET, queue):
        resp = change_email_unauthed_password(
            base_url="https://x.example", bearer_token="tok",
            new_email="new@example.invalid",
        )
    assert resp is None


def test_authorization_header_uses_bearer() -> None:
    """The bearer token must reach the outbound `Authorization`
    header in `Bearer <token>` form."""
    captured: dict = {}

    class _FakeClient:
        def __init__(self, **_kw): pass
        def __enter__(self): return self
        def __exit__(self, *_a): return None
        def post(self, url, *, headers, json):  # type: ignore[no-untyped-def]
            captured["headers"] = headers
            captured["json"] = json
            return _ok(200)

    with patch("apps.stubs.email_change_takeover.submit.Client", _FakeClient):
        change_email_unauthed_password(
            base_url="https://x.example", bearer_token="opaque-tok",
            new_email="new@example.invalid",
        )
    assert captured["headers"]["authorization"] == "Bearer opaque-tok"
    assert captured["json"] == {"new_email": "new@example.invalid"}
    assert "current_password" not in captured["json"]


# ---- bearer_token_from ----------------------------------------------

def _resp_with_body(body: object) -> MagicMock:
    r = MagicMock()
    r.json.return_value = body
    return r


def test_bearer_token_from_top_level_token() -> None:
    assert bearer_token_from(_resp_with_body({"token": "abc"})) == "abc"


def test_bearer_token_from_camelcase_access_token() -> None:
    assert bearer_token_from(
        _resp_with_body({"accessToken": "xyz"}),
    ) == "xyz"


def test_bearer_token_from_snake_case_access_token() -> None:
    assert bearer_token_from(
        _resp_with_body({"access_token": "snk"}),
    ) == "snk"


def test_bearer_token_from_nested_authentication() -> None:
    """Juice-Shop-style {"authentication": {"token": "..."}}."""
    payload = {"authentication": {"token": "nested-tok"}}
    assert bearer_token_from(_resp_with_body(payload)) == "nested-tok"


def test_bearer_token_priority_token_over_jwt() -> None:
    """`token` wins over `jwt` when both present (priority order)."""
    payload = {"token": "first", "jwt": "second"}
    assert bearer_token_from(_resp_with_body(payload)) == "first"


def test_bearer_token_missing_returns_none() -> None:
    assert bearer_token_from(_resp_with_body({"foo": "bar"})) is None


def test_bearer_token_non_json_returns_none() -> None:
    r = MagicMock()
    r.json.side_effect = ValueError("not json")
    assert bearer_token_from(r) is None


def test_bearer_token_empty_string_treated_as_missing() -> None:
    """An empty-string token isn't usable — treat as no token."""
    payload = {"token": ""}
    assert bearer_token_from(_resp_with_body(payload)) is None


def test_bearer_token_walk_bounded_by_max_depth() -> None:
    """The walker doesn't dig past depth=3 — sanity check that a
    deeply-nested token isn't found (and doesn't crash)."""
    payload = {"a": {"b": {"c": {"d": {"token": "too-deep"}}}}}
    assert bearer_token_from(_resp_with_body(payload)) is None
