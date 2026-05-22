"""Contract tests for IMAPMailbox construction and from_env validation."""
from __future__ import annotations

import pytest

from apps.stubs._shared.auth._imap import IMAPMailbox
from apps.stubs._shared.auth.mailbox import MailboxConfigError
from apps.stubs._shared.auth.tests._imap_helpers import _patch_imaplib


def test_construction_rejects_port_143() -> None:
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
