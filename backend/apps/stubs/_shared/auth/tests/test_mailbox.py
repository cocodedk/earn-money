"""Contract tests for `_shared/auth/mailbox` — Protocol + helpers.

Slice 01 of the mailbox-fixture plan tree. The IMAP backend is
exercised separately in `test_mailbox_imap.py`.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from apps.stubs._shared.auth.mailbox import (
    FakeMailbox, InboundMessage, MailboxConfigError, extract_link,
    extract_reset_token, load_mailbox_backend,
)


def _msg(
    *,
    to: str = "scanner@example.invalid",
    subject: str = "Reset your password",
    body_text: str = "",
    body_html: str = "",
    arrived_at: datetime | None = None,
    message_id: str = "abc@example.invalid",
) -> InboundMessage:
    return InboundMessage(
        to_address=to,
        from_address="noreply@target.invalid",
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        arrived_at=arrived_at or datetime.now(timezone.utc),
        message_id=message_id,
    )


# ----- InboundMessage shape -----------------------------------------

def test_inbound_message_is_frozen() -> None:
    msg = _msg()
    with pytest.raises(dataclasses.FrozenInstanceError):
        msg.subject = "altered"  # type: ignore[misc]


# ----- extract_reset_token ------------------------------------------

def test_extract_reset_token_finds_token_param() -> None:
    msg = _msg(body_text="Reset here: https://x.test/reset?token=abc123")
    assert extract_reset_token(msg) == "abc123"


def test_extract_reset_token_uses_html_when_text_empty() -> None:
    msg = _msg(
        body_text="",
        body_html='Reset: <a href="https://x.test/reset?token=html123">link</a>',
    )
    assert extract_reset_token(msg) == "html123"


def test_extract_reset_token_falls_through_to_code() -> None:
    msg = _msg(body_text="https://x.test/reset?code=via-code")
    assert extract_reset_token(msg) == "via-code"


def test_extract_reset_token_falls_through_to_t() -> None:
    msg = _msg(body_text="https://x.test/reset?t=short-t")
    assert extract_reset_token(msg) == "short-t"


def test_extract_reset_token_returns_none_when_url_missing_substring() -> None:
    msg = _msg(body_text="Welcome: https://x.test/dashboard?token=irrelevant")
    assert extract_reset_token(msg) is None


def test_extract_reset_token_returns_none_when_no_links() -> None:
    msg = _msg(body_text="No links here, just plain text.")
    assert extract_reset_token(msg) is None


def test_extract_reset_token_custom_url_substring() -> None:
    msg = _msg(body_text="https://x.test/verify-email?token=ver-tok")
    assert extract_reset_token(msg, url_substring="verify") == "ver-tok"


# ----- extract_link --------------------------------------------------

def test_extract_link_returns_first_matching_url() -> None:
    msg = _msg(body_text=(
        "First: https://x.test/other\n"
        "Second: https://x.test/reset?token=abc"
    ))
    assert extract_link(msg, url_substring="reset") == "https://x.test/reset?token=abc"


def test_extract_link_returns_none_when_no_match() -> None:
    msg = _msg(body_text="https://x.test/dashboard")
    assert extract_link(msg, url_substring="reset") is None


def test_extract_link_strips_trailing_punctuation() -> None:
    """Email clients often punctuate URLs. The helper must not include
    the trailing dot / paren / comma in the returned URL."""
    msg = _msg(body_text="Click https://x.test/reset?token=tail, then login.")
    link = extract_link(msg, url_substring="reset")
    assert link is not None
    assert link.endswith("tail")


# ----- FakeMailbox ---------------------------------------------------

def test_fake_mailbox_returns_first_matching_message() -> None:
    ts = datetime.now(timezone.utc)
    msgs = [
        _msg(to="other@example.invalid", arrived_at=ts),
        _msg(to="scanner@example.invalid", arrived_at=ts),
    ]
    mb = FakeMailbox(messages=msgs)
    out = mb.wait_for_message(
        "scanner@example.invalid",
        since=ts - timedelta(seconds=1),
        timeout_s=0.0,
    )
    assert out is not None
    assert out.to_address == "scanner@example.invalid"


def test_fake_mailbox_respects_since_cutoff() -> None:
    now = datetime.now(timezone.utc)
    old = _msg(arrived_at=now - timedelta(minutes=10))
    mb = FakeMailbox(messages=[old])
    out = mb.wait_for_message(
        "scanner@example.invalid", since=now, timeout_s=0.0,
    )
    assert out is None


def test_fake_mailbox_append_visible_after_construction() -> None:
    mb = FakeMailbox(messages=[])
    ts = datetime.now(timezone.utc)
    mb.append(_msg(arrived_at=ts))
    out = mb.wait_for_message(
        "scanner@example.invalid",
        since=ts - timedelta(seconds=1),
        timeout_s=0.0,
    )
    assert out is not None


# ----- load_mailbox_backend ------------------------------------------

def test_load_mailbox_backend_none_mode_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_BACKEND", "none")
    assert load_mailbox_backend() is None


def test_load_mailbox_backend_missing_env_raises(monkeypatch) -> None:
    monkeypatch.delenv("FIXTURE_MAILBOX_BACKEND", raising=False)
    with pytest.raises(MailboxConfigError, match="FIXTURE_MAILBOX_BACKEND"):
        load_mailbox_backend()


def test_load_mailbox_backend_unknown_value_raises(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_BACKEND", "carrier-pigeon")
    with pytest.raises(MailboxConfigError, match="carrier-pigeon"):
        load_mailbox_backend()


def test_load_mailbox_backend_mailosaur_not_implemented_yet(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_BACKEND", "mailosaur")
    with pytest.raises(MailboxConfigError, match="not yet implemented"):
        load_mailbox_backend()


def test_load_mailbox_backend_catchall_not_implemented_yet(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_BACKEND", "catchall")
    with pytest.raises(MailboxConfigError, match="not yet implemented"):
        load_mailbox_backend()


def test_extract_reset_token_returns_none_when_reset_url_has_no_recognized_param() -> None:
    """The reset URL is found but its query string contains none of the
    recognised token param names (token / code / t / k) → returns None."""
    msg = _msg(body_text="Click: https://x.test/reset?session_id=irrelevant")
    assert extract_reset_token(msg) is None
