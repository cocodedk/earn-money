"""Codex P2.1 + P1.2 tests for stub 2.10 submit helpers.

Split from test_submit.py once `verify_mfa_enrolled` + the
`_sensitive_paths` env-override coverage pushed the original file
past the 200-line cap.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from apps.stubs.mfa_bypass.submit import (
    _sensitive_paths, verify_mfa_enrolled,
)


def _resp_with_json(status: int, body) -> MagicMock:
    r = MagicMock(status_code=status)
    r.json.return_value = body
    return r


def _patch_get(responses: list):
    class _FakeClient:
        def __init__(self, **_kw): pass
        def __enter__(self): return self
        def __exit__(self, *_a): return None
        def get(self, url, *, headers):  # type: ignore[no-untyped-def]
            r = responses.pop(0)
            if isinstance(r, BaseException):
                raise r
            return r
    return patch("apps.stubs.mfa_bypass.submit.Client", _FakeClient)


# ---- verify_mfa_enrolled ---------------------------------------------

def test_verify_mfa_enrolled_true() -> None:
    queue = [_resp_with_json(200, {"email": "x", "mfaEnabled": True})]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is True


def test_verify_mfa_enrolled_snake_case() -> None:
    queue = [_resp_with_json(200, {"mfa_enabled": True})]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is True


def test_verify_mfa_enrolled_false() -> None:
    queue = [_resp_with_json(200, {"mfaEnabled": False})]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is False


def test_verify_mfa_enrolled_no_flag_field_returns_none() -> None:
    """No MFA-flag field → None (can't confirm). Previously False,
    which would let stub 2.13 false-positive on a profile that
    omits the field entirely (codex MFA-family P1)."""
    queue = [_resp_with_json(200, {"email": "x"})]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is None


def test_verify_mfa_enrolled_ambiguous_value_returns_none() -> None:
    """`mfaEnabled` present but the value is neither True nor False
    (e.g. "true" as a string) → None. The runner shouldn't act on
    ambiguous types."""
    queue = [_resp_with_json(200, {"mfaEnabled": "true"})]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is None


def test_verify_mfa_enrolled_404_skips() -> None:
    queue = [
        _resp_with_json(404, {}),
        _resp_with_json(200, {"mfaEnabled": True}),
    ]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is True


def test_verify_mfa_enrolled_non_2xx_returns_none() -> None:
    queue = [_resp_with_json(500, {})]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is None


def test_verify_mfa_enrolled_non_dict_body_returns_none() -> None:
    queue = [_resp_with_json(200, [1, 2, 3])]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is None


def test_verify_mfa_enrolled_invalid_json_returns_none() -> None:
    r = MagicMock(status_code=200)
    r.json.side_effect = ValueError("bad json")
    with _patch_get([r]):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is None


def test_verify_mfa_enrolled_all_404_returns_none() -> None:
    queue = [_resp_with_json(404, {}) for _ in range(6)]
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is None


def test_verify_mfa_enrolled_all_transport_errors_returns_none() -> None:
    queue: list = [httpx.ConnectError("boom")] * 6
    with _patch_get(queue):
        assert verify_mfa_enrolled(
            base_url="https://x.example", bearer_token="t",
        ) is None


# ---- _sensitive_paths env override -----------------------------------

def test_sensitive_paths_default(monkeypatch) -> None:
    """Default list contains only fixture-safe routes; destructive
    paths must NOT appear (codex P1.2)."""
    monkeypatch.delenv("FIXTURE_SENSITIVE_ACTION_PATHS", raising=False)
    paths = _sensitive_paths()
    assert "/sensitive-action" in paths
    assert "/api/sensitive-action" in paths
    assert not any("admin" in p or "delete" in p for p in paths)


def test_sensitive_paths_env_override(monkeypatch) -> None:
    """Operator-supplied env override → exactly the paths listed,
    whitespace trimmed, empty entries discarded."""
    monkeypatch.setenv(
        "FIXTURE_SENSITIVE_ACTION_PATHS", "/my/sensitive, /another, ",
    )
    assert _sensitive_paths() == ("/my/sensitive", "/another")
