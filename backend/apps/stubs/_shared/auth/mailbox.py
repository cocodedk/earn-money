"""Mailbox-fixture protocol + helpers.

The mailbox layer reads emails the target sends to scanner-owned
addresses. Six Phase 2 stubs (2.5 / 2.6 / 2.7 / 2.8 / 2.9 / 2.20)
depend on it.

Slice 01 ships the Protocol + extraction helpers + FakeMailbox.
Real backends (IMAP / Mailosaur / catchall) slot in via subsequent
slices through `load_mailbox_backend()` env-var dispatch.

Targets that don't send email at all (DVWA-style register-and-login)
use `FIXTURE_MAILBOX_BACKEND=none`; `load_mailbox_backend()` returns
None and the stub falls into its `no_mailbox_mode` branch.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from urllib.parse import parse_qs, urlsplit


# Order matters — `token` wins over `code` / `t` / `k` when multiple
# query params are present on the same URL.
_TOKEN_PARAM_PRIORITY: tuple[str, ...] = ("token", "code", "t", "k")

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_URL_TRAILING_PUNCT = ".,;:!?)]>"


class MailboxConfigError(Exception):
    """Raised when env-var config for the mailbox is missing,
    inconsistent, or names a backend that isn't wired yet."""


@dataclass(frozen=True)
class InboundMessage:
    """One email the target sent to a scanner-owned address.

    `body_text` is the decoded text/plain part; `body_html` the
    text/html part. Either may be empty. `arrived_at` is the
    server-side received timestamp, not the `Date:` header
    (clients can lie about Date)."""
    to_address: str
    from_address: str
    subject: str
    body_text: str
    body_html: str
    arrived_at: datetime
    message_id: str


class MailboxBackend(Protocol):
    """Read-only contract every backend implements."""

    def wait_for_message(
        self, to_address: str, *,
        since: datetime, timeout_s: float = 30.0,
    ) -> InboundMessage | None:
        ...  # pragma: no cover — Protocol body


def extract_reset_token(
    message: InboundMessage, *, url_substring: str = "reset",
) -> str | None:
    """Return the first URL containing ``url_substring`` and pull a
    token from its query string (preferring `token`, then `code`,
    then `t`, then `k`). None if no link matches or no recognised
    token param is present."""
    link = extract_link(message, url_substring=url_substring)
    if link is None:
        return None
    qs = parse_qs(urlsplit(link).query)
    for key in _TOKEN_PARAM_PRIORITY:
        if key in qs and qs[key]:
            return qs[key][0]
    return None


def extract_link(
    message: InboundMessage, *, url_substring: str,
) -> str | None:
    """Return the first URL in the message body that contains
    ``url_substring``. Searches text first, then HTML. Trailing
    punctuation that email clients append is stripped."""
    needle = url_substring.lower()
    for body in (message.body_text, message.body_html):
        for raw in _URL_RE.findall(body):
            cleaned = raw.rstrip(_URL_TRAILING_PUNCT)
            if needle in cleaned.lower():
                return cleaned
    return None


@dataclass
class FakeMailbox:
    """Test-only fixture. Production code never imports this."""
    messages: list[InboundMessage] = field(default_factory=list)

    def append(self, msg: InboundMessage) -> None:
        self.messages.append(msg)

    def wait_for_message(
        self, to_address: str, *,
        since: datetime, timeout_s: float = 30.0,
    ) -> InboundMessage | None:
        # Tests inject the list directly; we don't sleep. The
        # timeout_s arg is honoured by other backends that poll.
        for msg in self.messages:
            if msg.to_address == to_address and msg.arrived_at >= since:
                return msg
        return None


_BACKEND_ENV = "FIXTURE_MAILBOX_BACKEND"
_NOT_YET_IMPLEMENTED = {"mailosaur", "catchall"}


def load_mailbox_backend() -> MailboxBackend | None:
    """Construct the backend from env vars.

    Returns:
        - an IMAPMailbox when FIXTURE_MAILBOX_BACKEND=imap (slice 02)
        - a MailosaurMailbox when FIXTURE_MAILBOX_BACKEND=mailosaur
          (not yet implemented; raises)
        - a CatchallMailbox when FIXTURE_MAILBOX_BACKEND=catchall
          (not yet implemented; raises)
        - None when FIXTURE_MAILBOX_BACKEND=none — target doesn't
          send email and the stub falls into its no_mailbox_mode
          branch
    Raises:
        MailboxConfigError for any other value or missing env var.
    """
    backend = os.environ.get(_BACKEND_ENV)
    if not backend:
        raise MailboxConfigError(
            f"{_BACKEND_ENV} env var must be set "
            f"(values: imap | mailpit | mailosaur | catchall | none)"
        )
    if backend == "none":
        return None
    if backend == "imap":
        from ._imap import IMAPMailbox
        return IMAPMailbox.from_env()
    if backend == "mailpit":
        from ._mailpit import MailpitMailbox
        return MailpitMailbox.from_env()
    if backend in _NOT_YET_IMPLEMENTED:
        raise MailboxConfigError(
            f"FIXTURE_MAILBOX_BACKEND={backend!r}: backend spec'd but "
            f"not yet implemented; use 'imap' / 'mailpit' / 'none'"
        )
    raise MailboxConfigError(
        f"FIXTURE_MAILBOX_BACKEND={backend!r}: unknown backend "
        f"(values: imap | mailpit | mailosaur | catchall | none)"
    )
