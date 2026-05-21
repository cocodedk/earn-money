"""Unit tests for `mfa_bypass.submit`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from apps.stubs._shared.auth.tests._post_paths_helpers import patch_client
from apps.stubs.mfa_bypass.submit import enroll_mfa, post_sensitive_action


_TARGET = "apps.stubs.mfa_bypass.submit.Client"


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


def test_enroll_first_non_404() -> None:
    queue = [_ok(200), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = enroll_mfa(base_url="https://x.example", bearer_token="t")
    assert resp is not None and resp.status_code == 200


def test_enroll_skips_404() -> None:
    queue = [_ok(404), _ok(405), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = enroll_mfa(base_url="https://x.example", bearer_token="t")
    assert resp is not None and resp.status_code == 200


def test_enroll_all_transport_errors() -> None:
    queue: list = [httpx.ConnectError("boom")] * 5
    with patch_client(_TARGET, queue):
        resp = enroll_mfa(base_url="https://x.example", bearer_token="t")
    assert resp is None


def test_enroll_all_404_returns_last() -> None:
    queue = [_ok(404)] * 5
    with patch_client(_TARGET, queue):
        resp = enroll_mfa(base_url="https://x.example", bearer_token="t")
    assert resp is not None and resp.status_code == 404


def test_sensitive_first_non_404() -> None:
    queue = [_ok(200)]
    with patch_client(_TARGET, queue):
        resp = post_sensitive_action(
            base_url="https://x.example", bearer_token="t",
        )
    assert resp is not None and resp.status_code == 200


def test_sensitive_authorization_header_propagates() -> None:
    """The bearer reaches `Authorization: Bearer <token>` and the
    outbound body has no MFA step-up header."""
    captured: dict = {}

    class _FakeClient:
        def __init__(self, **_kw): pass
        def __enter__(self): return self
        def __exit__(self, *_a): return None
        def post(self, url, *, headers, json):  # type: ignore[no-untyped-def]
            captured["headers"] = headers
            captured["json"] = json
            return _ok(200)

    with patch("apps.stubs.mfa_bypass.submit.Client", _FakeClient):
        post_sensitive_action(
            base_url="https://x.example", bearer_token="opaque",
        )
    assert captured["headers"]["authorization"] == "Bearer opaque"
    assert captured["json"] == {}
    # The load-bearing assertion: NO step-up header on the wire.
    for h in captured["headers"]:
        assert "mfa" not in h.lower()
        assert "step-up" not in h.lower()
        assert "otp" not in h.lower()

