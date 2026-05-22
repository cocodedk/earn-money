"""Shared helpers for IMAP test files."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

__all__ = ["_fake_imap_returning", "_patch_imaplib"]


def _fake_imap_returning(*, search_uids: bytes, fetch_body: bytes) -> MagicMock:
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
