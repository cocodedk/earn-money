"""Contract tests for `_shared/auth/_imap.IMAPMailbox`.

Uses an in-memory fake IMAP4_SSL stand-in patched into imaplib.
No real network. Real-IMAP smoke is `scripts/smoke_mailbox.py`,
not unit-tested in CI.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from apps.stubs._shared.auth._imap import IMAPMailbox
from apps.stubs._shared.auth.mailbox import MailboxConfigError


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


def _fake_imap_returning(*, search_uids: bytes, fetch_body: bytes) -> MagicMock:
    """Return a MagicMock that mimics imaplib.IMAP4_SSL with a one-shot
    SEARCH + FETCH cycle."""
    imap = MagicMock()
    imap.login.return_value = ("OK", [b"Logged in"])
    imap.select.return_value = ("OK", [b"1"])
    imap.search.return_value = ("OK", [search_uids])
    imap.fetch.return_value = (
        "OK",
        [(b"1 (RFC822 {123}", fetch_body), b")"],
    )
    imap.logout.return_value = ("BYE", [b""])
    return imap


def _patch_imaplib(imap_mock: MagicMock):
    return patch(
        "apps.stubs._shared.auth._imap.imaplib.IMAP4_SSL",
        return_value=imap_mock,
    )


# ----- construction errors ------------------------------------------

def test_construction_rejects_port_143() -> None:
    """Plain IMAP (port 143) is refused — TLS only."""
    with pytest.raises(MailboxConfigError, match="143"):
        IMAPMailbox(host="imap.example", port=143,
                    user="u@example.test", password="pw")


def test_from_env_requires_user(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_HOST", "imap.example")
    monkeypatch.delenv("FIXTURE_MAILBOX_IMAP_USER", raising=False)
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_PASSWORD", "pw")
    with pytest.raises(MailboxConfigError, match="FIXTURE_MAILBOX_IMAP_USER"):
        IMAPMailbox.from_env()


def test_from_env_requires_host(monkeypatch) -> None:
    monkeypatch.delenv("FIXTURE_MAILBOX_IMAP_HOST", raising=False)
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_USER", "u@example.test")
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_PASSWORD", "pw")
    with pytest.raises(MailboxConfigError, match="FIXTURE_MAILBOX_IMAP_HOST"):
        IMAPMailbox.from_env()


def test_from_env_requires_password(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_HOST", "imap.example")
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_USER", "u@example.test")
    monkeypatch.delenv("FIXTURE_MAILBOX_IMAP_PASSWORD", raising=False)
    with pytest.raises(MailboxConfigError, match="FIXTURE_MAILBOX_IMAP_PASSWORD"):
        IMAPMailbox.from_env()


def test_from_env_default_port_993(monkeypatch) -> None:
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_HOST", "imap.example")
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_USER", "u@example.test")
    monkeypatch.setenv("FIXTURE_MAILBOX_IMAP_PASSWORD", "pw")
    monkeypatch.delenv("FIXTURE_MAILBOX_IMAP_PORT", raising=False)
    mb = IMAPMailbox.from_env()
    assert mb.port == 993


# ----- happy-path wait_for_message ----------------------------------

def test_wait_for_message_returns_parsed_inbound() -> None:
    since = datetime(2026, 5, 21, 11, 0, tzinfo=timezone.utc)
    imap = _fake_imap_returning(
        search_uids=b"1",
        fetch_body=SAMPLE_RESET_EMAIL,
    )
    with _patch_imaplib(imap):
        mb = IMAPMailbox(host="imap.example", port=993,
                         user="u@example.test", password="pw")
        msg = mb.wait_for_message(
            "scanner@example.invalid",
            since=since, timeout_s=0.1,
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
    import imaplib
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
    """A message that arrived BEFORE `since` is rejected even when
    the IMAP search returns it (IMAP SINCE is date-level; we filter
    by wall-clock on the Python side for sub-day precision)."""
    cutoff = datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc)
    # SAMPLE_RESET_EMAIL has Date: 12:00, before cutoff at 13:00
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


# ----- load_mailbox_backend wiring ----------------------------------

def test_load_mailbox_backend_imap_returns_imap_mailbox(monkeypatch) -> None:
    """`FIXTURE_MAILBOX_BACKEND=imap` + full IMAP env → IMAPMailbox."""
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
