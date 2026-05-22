"""Shared helpers for IMAP test files."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

__all__ = ["_patch_imaplib"]


def _patch_imaplib(imap_mock: MagicMock):
    return patch(
        "apps.stubs._shared.auth._imap.imaplib.IMAP4_SSL",
        return_value=imap_mock,
    )
