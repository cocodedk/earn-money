"""Unit tests for `_shared/auth/_mailpit.MailpitMailbox`."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.stubs._shared.auth._mailpit import MailpitMailbox
from apps.stubs._shared.auth.mailbox import (
    MailboxConfigError, load_mailbox_backend,
)


_NOW = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)


def _msg_entry(*, mid: str, created: str) -> dict:
    return {
        "ID": mid,
        "Created": created,
        "From": {"Address": "noreply@reset-canary.local"},
        "To": [{"Address": "scanner@example.invalid"}],
        "Subject": "Reset",
    }


def _full_msg(*, mid: str, text: str) -> dict:
    return {
        "ID": mid,
        "MessageID": f"<{mid}@reset-canary.local>",
        "Date": "2026-05-21T12:00:01Z",
        "From": {"Address": "noreply@reset-canary.local"},
        "To": [{"Address": "scanner@example.invalid"}],
        "Subject": "Reset",
        "Text": text,
        "HTML": f"<a>{text}</a>",
    }


def _patch_client(responses: list):
    """Patch Client so each `with Client(...) as c: c.get(...)` pops
    from the shared queue. Each entry is a MagicMock response."""
    class _FakeClient:
        def __init__(self, **_kw: object) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def get(self, url: str, params: dict | None = None):  # type: ignore[no-untyped-def]
            r = responses.pop(0)
            if isinstance(r, BaseException):
                raise r
            return r

    return patch("apps.stubs._shared.auth._mailpit.Client", _FakeClient)


def _ok(payload: dict) -> MagicMock:
    r = MagicMock(status_code=200)
    r.json.return_value = payload
    return r


def test_from_env_requires_url(monkeypatch) -> None:
    monkeypatch.delenv("FIXTURE_MAILBOX_MAILPIT_URL", raising=False)
    with pytest.raises(MailboxConfigError, match="FIXTURE_MAILBOX_MAILPIT_URL"):
        MailpitMailbox.from_env()


def test_from_env_strips_trailing_slash(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_MAILPIT_URL", "http://mailpit:8025/")
    box = MailpitMailbox.from_env()
    assert box.base_url == "http://mailpit:8025"


def test_wait_returns_message_when_present() -> None:
    """search returns one entry → fetch full message → return parsed."""
    search = _ok({"messages": [
        _msg_entry(mid="abc", created="2026-05-21T12:00:00.5Z"),
    ]})
    full = _ok(_full_msg(mid="abc", text="reset link inside"))
    with _patch_client([search, full]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.01,
        )
    assert msg is not None
    assert msg.to_address == "scanner@example.invalid"
    assert msg.body_text == "reset link inside"
    assert msg.message_id == "<abc@reset-canary.local>"


def test_wait_skips_message_older_than_since() -> None:
    """Entry's Created is BEFORE `since` → ignored, returns None on
    timeout."""
    search = _ok({"messages": [
        _msg_entry(mid="old", created="2025-01-01T00:00:00Z"),
    ]})
    with _patch_client([search]), \
         patch("apps.stubs._shared.auth._mailpit.time.sleep"), \
         patch("apps.stubs._shared.auth._mailpit.time.monotonic",
               side_effect=[0.0, 1.0]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.5,
        )
    assert msg is None


def test_wait_handles_empty_search() -> None:
    """Empty messages list → poll, sleep, poll again, then None on
    timeout. Exercises the inter-poll sleep branch."""
    search1 = _ok({"messages": []})
    search2 = _ok({"messages": []})
    with _patch_client([search1, search2]), \
         patch("apps.stubs._shared.auth._mailpit.time.sleep") as sleep_p, \
         patch("apps.stubs._shared.auth._mailpit.time.monotonic",
               side_effect=[0.0, 0.4, 1.0]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.5,
        )
    assert msg is None
    sleep_p.assert_called_once()


def test_wait_handles_search_transport_error() -> None:
    """search GET raises → poll returns None, loop continues until
    timeout."""
    with _patch_client([httpx.ConnectError("nope")]), \
         patch("apps.stubs._shared.auth._mailpit.time.sleep"), \
         patch("apps.stubs._shared.auth._mailpit.time.monotonic",
               side_effect=[0.0, 1.0]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.5,
        )
    assert msg is None


def test_wait_handles_search_non_200() -> None:
    """search GET returns 500 → treated as no-results, loop continues."""
    fail = MagicMock(status_code=500)
    with _patch_client([fail]), \
         patch("apps.stubs._shared.auth._mailpit.time.sleep"), \
         patch("apps.stubs._shared.auth._mailpit.time.monotonic",
               side_effect=[0.0, 1.0]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.5,
        )
    assert msg is None


def test_fetch_message_transport_error_returns_none() -> None:
    """search succeeds but full-message fetch transport-fails → None."""
    search = _ok({"messages": [
        _msg_entry(mid="abc", created="2026-05-21T12:00:00.5Z"),
    ]})
    with _patch_client([search, httpx.ConnectError("boom")]), \
         patch("apps.stubs._shared.auth._mailpit.time.sleep"), \
         patch("apps.stubs._shared.auth._mailpit.time.monotonic",
               side_effect=[0.0, 1.0]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.5,
        )
    assert msg is None


def test_fetch_message_non_200_returns_none() -> None:
    """search succeeds but full-message fetch returns 404 → None."""
    search = _ok({"messages": [
        _msg_entry(mid="abc", created="2026-05-21T12:00:00.5Z"),
    ]})
    fail = MagicMock(status_code=404)
    with _patch_client([search, fail]), \
         patch("apps.stubs._shared.auth._mailpit.time.sleep"), \
         patch("apps.stubs._shared.auth._mailpit.time.monotonic",
               side_effect=[0.0, 1.0]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.5,
        )
    assert msg is None


def test_unparseable_created_skipped() -> None:
    """Entry with garbled Created timestamp → ignored."""
    search = _ok({"messages": [
        _msg_entry(mid="bad", created="not-a-date"),
    ]})
    with _patch_client([search]), \
         patch("apps.stubs._shared.auth._mailpit.time.sleep"), \
         patch("apps.stubs._shared.auth._mailpit.time.monotonic",
               side_effect=[0.0, 1.0]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.5,
        )
    assert msg is None


def test_full_message_with_missing_date_uses_now() -> None:
    """Full message has no Date field → arrived_at falls back to now."""
    search = _ok({"messages": [
        _msg_entry(mid="abc", created="2026-05-21T12:00:00.5Z"),
    ]})
    payload = _full_msg(mid="abc", text="x")
    del payload["Date"]
    with _patch_client([search, _ok(payload)]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.01,
        )
    assert msg is not None
    # Just check it parsed something — exact value depends on clock.
    assert msg.arrived_at.tzinfo is not None


def test_full_message_without_to_list() -> None:
    """Full message with empty `To` array → to_address is empty
    string (graceful handling, not a crash)."""
    search = _ok({"messages": [
        _msg_entry(mid="abc", created="2026-05-21T12:00:00.5Z"),
    ]})
    payload = _full_msg(mid="abc", text="x")
    payload["To"] = []
    with _patch_client([search, _ok(payload)]):
        msg = MailpitMailbox(base_url="http://m").wait_for_message(
            "scanner@example.invalid", since=_NOW, timeout_s=0.01,
        )
    assert msg is not None
    assert msg.to_address == ""


def test_load_mailbox_backend_dispatches_to_mailpit(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_BACKEND", "mailpit")
    monkeypatch.setenv("FIXTURE_MAILBOX_MAILPIT_URL", "http://mailpit:8025")
    backend = load_mailbox_backend()
    assert isinstance(backend, MailpitMailbox)
    assert backend.base_url == "http://mailpit:8025"
