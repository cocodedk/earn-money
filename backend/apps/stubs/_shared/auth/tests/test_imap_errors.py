"""Error-path tests for `_shared/auth/_imap`.

Covers the branches not reached by test_mailbox_imap.py:
- OSError on IMAP4_SSL connect → MailboxConfigError
- logout raises IMAP4.error / OSError → swallowed
- conn.fetch returns non-OK → _fetch_and_parse returns None
- _extract_rfc822_payload payload is None when no tuple entry
- _extract_rfc822_payload: entry not a tuple, tuple payload not bytes, loop exhausted → None
- _parse_arrived with no Date header → utcnow fallback
- _decoded_text fallback when get_content() raises
"""
from __future__ import annotations

import email
import email.policy
import imaplib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from apps.stubs._shared.auth._imap import (
    IMAPMailbox,
    _extract_rfc822_payload,
    _parse_arrived,
    _decoded_text,
)
from apps.stubs._shared.auth.mailbox import MailboxConfigError
from apps.stubs._shared.auth.tests._imap_helpers import (
    _fake_imap_returning, _patch_imaplib,
)


def test_oserror_on_connect_raises_mailbox_config_error() -> None:
    """An OSError (e.g. refused connection) on IMAP4_SSL() is wrapped
    in MailboxConfigError so callers don't see raw socket errors."""
    with patch(
        "apps.stubs._shared.auth._imap.imaplib.IMAP4_SSL",
        side_effect=OSError("Connection refused"),
    ):
        mb = IMAPMailbox(
            host="imap.example", port=993,
            user="u@example.test", password="pw",
        )
        with pytest.raises(MailboxConfigError, match="IMAP connect"):
            mb.wait_for_message(
                "scanner@example.invalid",
                since=datetime.now(timezone.utc),
                timeout_s=0.1,
            )


def test_logout_error_is_swallowed() -> None:
    """When conn.logout() raises IMAP4.error, the exception is caught
    and the outer function still returns normally (no propagation)."""
    imap = _fake_imap_returning(search_uids=b"", fetch_body=b"")
    imap.logout.side_effect = imaplib.IMAP4.error("already logged out")

    with _patch_imaplib(imap):
        mb = IMAPMailbox(
            host="imap.example", port=993,
            user="u@example.test", password="pw",
        )
        result = mb.wait_for_message(
            "scanner@example.invalid",
            since=datetime.now(timezone.utc),
            timeout_s=0.1,
        )
    assert result is None  # clean return even though logout raised


def test_logout_oserror_is_swallowed() -> None:
    """An OSError from logout is also swallowed."""
    imap = _fake_imap_returning(search_uids=b"", fetch_body=b"")
    imap.logout.side_effect = OSError("broken pipe")

    with _patch_imaplib(imap):
        mb = IMAPMailbox(
            host="imap.example", port=993,
            user="u@example.test", password="pw",
        )
        result = mb.wait_for_message(
            "scanner@example.invalid",
            since=datetime.now(timezone.utc),
            timeout_s=0.1,
        )
    assert result is None


def test_fetch_non_ok_returns_none() -> None:
    """When conn.fetch() returns a non-OK status, _fetch_and_parse
    returns None — the UID is silently skipped."""
    imap = _fake_imap_returning(search_uids=b"1", fetch_body=b"")
    imap.fetch.return_value = ("NO", [])

    with _patch_imaplib(imap):
        mb = IMAPMailbox(
            host="imap.example", port=993,
            user="u@example.test", password="pw",
        )
        result = mb.wait_for_message(
            "scanner@example.invalid",
            since=datetime.now(timezone.utc),
            timeout_s=0.1,
        )
    assert result is None


def test_extract_rfc822_payload_returns_none_for_non_tuple_entries() -> None:
    """All entries in the FETCH data list are plain bytes (not tuples)
    → no payload tuple found → returns None."""
    assert _extract_rfc822_payload([b"literal string", b"another"]) is None


def test_extract_rfc822_payload_returns_none_for_empty_list() -> None:
    """Empty data list → None."""
    assert _extract_rfc822_payload([]) is None


def test_extract_rfc822_payload_skips_tuple_with_non_bytes_payload() -> None:
    """A tuple whose second element is not bytes is skipped."""
    data = [(b"header", "string payload"), (b"header2", None)]
    assert _extract_rfc822_payload(data) is None


def test_extract_rfc822_payload_skips_empty_bytes_payload() -> None:
    """A tuple with an empty bytes payload is treated as absent."""
    data = [(b"header", b"")]
    assert _extract_rfc822_payload(data) is None


def test_fetch_with_null_payload_returns_none() -> None:
    """When the FETCH response has OK status but data contains no valid
    RFC822 payload, _fetch_and_parse returns None and the outer loop
    ends with None."""
    imap = _fake_imap_returning(search_uids=b"1", fetch_body=b"")
    imap.fetch.return_value = ("OK", [b"no tuple here"])

    with _patch_imaplib(imap):
        mb = IMAPMailbox(
            host="imap.example", port=993,
            user="u@example.test", password="pw",
        )
        result = mb.wait_for_message(
            "scanner@example.invalid",
            since=datetime.now(timezone.utc),
            timeout_s=0.1,
        )
    assert result is None


def test_parse_arrived_returns_utcnow_when_date_missing() -> None:
    """When the Date header is absent (None), _parse_arrived returns a
    timezone-aware datetime close to now rather than raising."""
    before = datetime.now(timezone.utc)
    result = _parse_arrived(None)
    after = datetime.now(timezone.utc)
    assert before <= result <= after
    assert result.tzinfo is not None


def test_decode_text_fallback_on_get_content_exception() -> None:
    """When part.get_content() raises, _decoded_text falls back to
    part.get_payload(decode=True).decode('utf-8', errors='replace')."""
    part = MagicMock()
    part.get_content.side_effect = LookupError("unknown charset")
    part.get_payload.return_value = b"fallback content"
    result = _decoded_text(part)
    assert result == "fallback content"
