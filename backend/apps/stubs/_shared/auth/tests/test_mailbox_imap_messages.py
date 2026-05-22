"""Contract tests for IMAPMailbox.wait_for_message and mailbox wiring."""
from __future__ import annotations

import imaplib
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from apps.stubs._shared.auth._imap import IMAPMailbox
from apps.stubs._shared.auth.mailbox import MailboxConfigError
from apps.stubs._shared.auth.tests._imap_helpers import (
    _fake_imap_returning, _patch_imaplib,
)


SAMPLE_RESET_EMAIL = (
    b"From: noreply@target.invalid\r\n"
    b"To: scanner@example.invalid\r\n"
    b"Subject: Reset your password\r\n"
    b"Date: Wed, 21 May 2026 12:00:00 +0000\r\n"
    b"Message-ID: <abc@target.invalid>\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"\r\n"
    b"Click here to reset: https://target.invalid/reset?token=samp-tok\r\n"
)


def test_wait_for_message_returns_parsed_inbound() -> None:
    since = datetime(2026, 5, 21, 11, 0, tzinfo=timezone.utc)
    imap = _fake_imap_returning(search_uids=b"1", fetch_body=SAMPLE_RESET_EMAIL)
    with _patch_imaplib(imap):
        mb = IMAPMailbox(host="imap.example", port=993,
                         user="u@example.test", password="pw")
        msg = mb.wait_for_message(
            "scanner@example.invalid", since=since, timeout_s=0.1,
        )
    assert msg is not None
    assert msg.to_address == "scanner@example.invalid"
    assert msg.from_address == "noreply@target.invalid"
    assert msg.subject == "Reset your password"
    assert "samp-tok" in msg.body_text
    assert msg.message_id == "<abc@target.invalid>"


def test_wait_for_message_empty_search_returns_none() -> None:
    since = datetime.now(timezone.utc)
    imap = _fake_imap_returning(search_uids=b"", fetch_body=b"")
    with _patch_imaplib(imap):
        mb = IMAPMailbox(host="imap.example", port=993,
                         user="u@example.test", password="pw")
        msg = mb.wait_for_message(
            "scanner@example.invalid", since=since, timeout_s=0.1,
        )
    assert msg is None


def test_wait_for_message_login_failure_raises_config_error() -> None:
    imap = MagicMock()
    imap.login.side_effect = imaplib.IMAP4.error("bad credentials")
    with _patch_imaplib(imap):
        mb = IMAPMailbox(host="imap.example", port=993,
                         user="u@example.test", password="pw")
        with pytest.raises(MailboxConfigError, match="bad credentials"):
            mb.wait_for_message(
                "scanner@example.invalid",
                since=datetime.now(timezone.utc), timeout_s=0.1,
            )


def test_wait_for_message_filters_older_messages_by_since() -> None:
    """IMAP SINCE is date-level; Python side filters by wall-clock."""
    cutoff = datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc)
    imap = _fake_imap_returning(search_uids=b"1", fetch_body=SAMPLE_RESET_EMAIL)
    with _patch_imaplib(imap):
        mb = IMAPMailbox(host="imap.example", port=993,
                         user="u@example.test", password="pw")
        msg = mb.wait_for_message(
            "scanner@example.invalid", since=cutoff, timeout_s=0.1,
        )
    assert msg is None


def test_wait_for_message_quoted_printable_body_decoded() -> None:
    qp_email = (
        b"From: noreply@target.invalid\r\n"
        b"To: scanner@example.invalid\r\n"
        b"Subject: Reset\r\n"
        b"Date: Wed, 21 May 2026 12:00:00 +0000\r\n"
        b"Message-ID: <qp@target.invalid>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"Content-Transfer-Encoding: quoted-printable\r\n"
        b"\r\n"
        b"Click here =3D> https://x.test/reset=3Ftoken=3Dqp\r\n"
    )
    since = datetime(2026, 5, 21, 11, 0, tzinfo=timezone.utc)
    imap = _fake_imap_returning(search_uids=b"1", fetch_body=qp_email)
    with _patch_imaplib(imap):
        mb = IMAPMailbox(host="imap.example", port=993,
                         user="u@example.test", password="pw")
        msg = mb.wait_for_message(
            "scanner@example.invalid", since=since, timeout_s=0.1,
        )
    assert msg is not None
    assert "https://x.test/reset?token=qp" in msg.body_text


def test_wait_for_message_html_and_text_both_captured() -> None:
    multipart = (
        b"From: noreply@target.invalid\r\n"
        b"To: scanner@example.invalid\r\n"
        b"Subject: Reset\r\n"
        b"Date: Wed, 21 May 2026 12:00:00 +0000\r\n"
        b"Message-ID: <mp@target.invalid>\r\n"
        b'Content-Type: multipart/alternative; boundary="bdy"\r\n'
        b"\r\n"
        b"--bdy\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"plain-body\r\n"
        b"--bdy\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"\r\n"
        b"<p>html-body</p>\r\n"
        b"--bdy--\r\n"
    )
    since = datetime(2026, 5, 21, 11, 0, tzinfo=timezone.utc)
    imap = _fake_imap_returning(search_uids=b"1", fetch_body=multipart)
    with _patch_imaplib(imap):
        mb = IMAPMailbox(host="imap.example", port=993,
                         user="u@example.test", password="pw")
        msg = mb.wait_for_message(
            "scanner@example.invalid", since=since, timeout_s=0.1,
        )
    assert msg is not None
    assert "plain-body" in msg.body_text
    assert "html-body" in msg.body_html


def test_load_mailbox_backend_imap_returns_imap_mailbox(monkeypatch) -> None:
    from apps.stubs._shared.auth.mailbox import load_mailbox_backend
    monkeypatch.setenv("FIXTURE_MAILBOX_BACKEND", "imap")
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_HOST", "imap.example")
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_USER", "u@example.test")
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_PASSWORD", "pw")
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_PORT", "993")
    backend = load_mailbox_backend()
    assert isinstance(backend, IMAPMailbox)
    assert backend.host == "imap.example"
    assert backend.user == "u@example.test"
