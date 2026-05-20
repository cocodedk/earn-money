"""IMAPMailbox — reads emails from a real IMAP server.

stdlib `imaplib` + `email`; no third-party deps. New connection
per `wait_for_message` call (long-lived IMAP sockets are flaky
against bot-detection). TLS only — port 143 refused.

Polling cadence: 2.5 s between IMAP SEARCH cycles, up to
`timeout_s`. IMAP `SINCE` is date-level; sub-day precision comes
from filtering by the message `Date:` header on the Python side.
"""
from __future__ import annotations

import email
import email.policy
import imaplib
import os
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

from .mailbox import InboundMessage, MailboxConfigError


_POLL_INTERVAL_S = 2.5


@dataclass
class IMAPMailbox:
    """IMAP-over-TLS mailbox client."""
    host: str
    port: int
    user: str
    password: str

    def __post_init__(self) -> None:
        if self.port == 143:
            raise MailboxConfigError(
                "port 143 (plain IMAP) is refused; TLS-only (993)"
            )

    @classmethod
    def from_env(cls) -> "IMAPMailbox":
        host = os.environ.get("FIXTURE_MAILBOX_IMAP_HOST")
        if not host:
            raise MailboxConfigError("FIXTURE_MAILBOX_IMAP_HOST not set")
        user = os.environ.get("FIXTURE_MAILBOX_IMAP_USER")
        if not user:
            raise MailboxConfigError("FIXTURE_MAILBOX_IMAP_USER not set")
        password = os.environ.get("FIXTURE_MAILBOX_IMAP_PASSWORD")
        if not password:
            raise MailboxConfigError(
                "FIXTURE_MAILBOX_IMAP_PASSWORD not set"
            )
        port = int(os.environ.get("FIXTURE_MAILBOX_IMAP_PORT", "993"))
        return cls(host=host, port=port, user=user, password=password)

    def wait_for_message(
        self, to_address: str, *,
        since: datetime, timeout_s: float = 30.0,
    ) -> InboundMessage | None:
        deadline = time.monotonic() + timeout_s
        while True:
            match = self._poll_once(to_address=to_address, since=since)
            if match is not None:
                return match
            if time.monotonic() >= deadline:
                return None
            time.sleep(min(_POLL_INTERVAL_S, max(0.0, deadline - time.monotonic())))

    def _poll_once(
        self, *, to_address: str, since: datetime,
    ) -> InboundMessage | None:
        """One SEARCH + FETCH cycle. Caller loops + sleeps."""
        try:
            conn = imaplib.IMAP4_SSL(self.host, self.port)
        except OSError as exc:
            raise MailboxConfigError(
                f"IMAP connect to {self.host}:{self.port} failed: {exc}"
            ) from exc
        try:
            try:
                conn.login(self.user, self.password)
            except imaplib.IMAP4.error as exc:
                raise MailboxConfigError(str(exc)) from exc
            conn.select("INBOX")
            since_str = since.strftime("%d-%b-%Y")
            criterion = f'(TO "{to_address}" SINCE {since_str})'
            typ, data = conn.search(None, criterion)
            if typ != "OK" or not data or not data[0]:
                return None
            for uid in data[0].split():
                msg = self._fetch_and_parse(conn, uid)
                if msg is not None and msg.arrived_at >= since:
                    return msg
            return None
        finally:
            try:
                conn.logout()
            except (imaplib.IMAP4.error, OSError):
                pass

    @staticmethod
    def _fetch_and_parse(conn, uid: bytes) -> InboundMessage | None:
        typ, data = conn.fetch(uid, "(RFC822)")
        if typ != "OK" or not data:
            return None
        raw = _extract_rfc822_payload(data)
        if raw is None:
            return None
        parsed = email.message_from_bytes(raw, policy=email.policy.default)
        return _to_inbound(parsed)


def _extract_rfc822_payload(data: list) -> bytes | None:
    """imaplib's fetch returns a list whose entries are either
    bytes or (envelope_bytes, payload_bytes) tuples. Pick the
    first payload."""
    for entry in data:
        if isinstance(entry, tuple) and len(entry) >= 2:
            payload = entry[1]
            if isinstance(payload, bytes) and payload:
                return payload
    return None


def _to_inbound(parsed: email.message.Message) -> InboundMessage:
    """Convert a parsed `email.message.Message` to InboundMessage."""
    to_addr = _addr(parsed.get("To", ""))
    from_addr = _addr(parsed.get("From", ""))
    subject = str(parsed.get("Subject", "") or "")
    arrived = _parse_arrived(parsed.get("Date"))
    message_id = str(parsed.get("Message-ID", "") or "")
    body_text, body_html = _extract_bodies(parsed)
    return InboundMessage(
        to_address=to_addr,
        from_address=from_addr,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        arrived_at=arrived,
        message_id=message_id,
    )


def _addr(raw: str) -> str:
    """Strip the display-name part so the address compares cleanly."""
    from email.utils import parseaddr
    return parseaddr(raw)[1].strip().lower()


def _parse_arrived(date_header: str | None) -> datetime:
    if not date_header:
        from datetime import timezone
        return datetime.now(timezone.utc)
    return parsedate_to_datetime(date_header)


def _extract_bodies(msg: email.message.Message) -> tuple[str, str]:
    """Walk a multipart message and pull text/plain + text/html
    parts. Either may be empty."""
    body_text = ""
    body_html = ""
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "text/plain" and not body_text:
            body_text = _decoded_text(part)
        elif ctype == "text/html" and not body_html:
            body_html = _decoded_text(part)
    return body_text, body_html


def _decoded_text(part: email.message.Message) -> str:
    try:
        return part.get_content() or ""
    except Exception:
        # Fallback for malformed parts — best-effort decode.
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")
