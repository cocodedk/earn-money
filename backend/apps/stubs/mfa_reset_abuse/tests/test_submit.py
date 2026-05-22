"""Unit tests for `mfa_reset_abuse.submit.disable_mfa`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from apps.stubs._shared.auth.tests._post_paths_helpers import patch_client
from apps.stubs.mfa_reset_abuse.submit import disable_mfa


_TARGET = "apps.stubs.mfa_reset_abuse.submit.Client"


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


def test_first_non_404_returned() -> None:
    queue = [_ok(200), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = disable_mfa(base_url="https://x.example", bearer_token="t")
    assert resp is not None and resp.status_code == 200


def test_skips_404_and_405() -> None:
    queue = [_ok(404), _ok(405), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = disable_mfa(base_url="https://x.example", bearer_token="t")
    assert resp is not None and resp.status_code == 200


def test_all_404_returns_last() -> None:
    queue = [_ok(404)] * 4
    with patch_client(_TARGET, queue):
        resp = disable_mfa(base_url="https://x.example", bearer_token="t")
    assert resp is not None and resp.status_code == 404


def test_all_transport_errors_returns_none() -> None:
    queue: list = [httpx.ConnectError("boom")] * 4
    with patch_client(_TARGET, queue):
        resp = disable_mfa(base_url="https://x.example", bearer_token="t")
    assert resp is None


def test_authorization_header_and_no_step_up_body() -> None:
    """The bearer hits `Authorization: Bearer <token>` and the
    outbound body has NO current_password / step-up field — that's
    the whole point of the probe (codex P1.2 mirror)."""
    captured: dict = {}

    class _FakeClient:
        def __init__(self, **_kw): pass
        def __enter__(self): return self
        def __exit__(self, *_a): return None
        def post(self, url, *, headers, json):  # type: ignore[no-untyped-def]
            captured["headers"] = headers
            captured["json"] = json
            return _ok(200)

    with patch("apps.stubs.mfa_reset_abuse.submit.Client", _FakeClient):
        disable_mfa(base_url="https://x.example", bearer_token="opaque")
    assert captured["headers"]["authorization"] == "Bearer opaque"
    assert captured["json"] == {}
    for h in captured["headers"]:
        assert "step-up" not in h.lower()
        assert "mfa-otp" not in h.lower()
