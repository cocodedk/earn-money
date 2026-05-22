"""MailpitMailbox — reads emails from a Mailpit sidecar via REST.

Mailpit's IMAP server is plaintext-only; the platform's IMAPMailbox
refuses port 143 by design. The REST API (default port 8025) is the
operator-intended surface for programmatic access:
    GET /api/v1/search?query=to:<addr>  → message list
    GET /api/v1/message/<ID>            → full body (Text + HTML)

New httpx connection per call; the API is stateless. Polling cadence
is faster than IMAP (1.0 s) because the API is local-network.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from httpx import Client

from ._poll import poll_until
from .mailbox import InboundMessage, MailboxConfigError


_POLL_INTERVAL_S = 1.0
_DEFAULT_TIMEOUT = 5.0


@dataclass
class MailpitMailbox:
    """REST client for a Mailpit instance on the local docker network."""
    base_url: str

    @classmethod
    def from_env(cls) -> "MailpitMailbox":
        base = os.environ.get("FIXTURE_MAILBOX_MAILPIT_URL")
        if not base:
            raise MailboxConfigError(
                "FIXTURE_MAILBOX_MAILPIT_URL not set "
                "(e.g. http://mailpit:8025)"
            )
        return cls(base_url=base.rstrip("/"))

    def wait_for_message(
        self, to_address: str, *,
        since: datetime, timeout_s: float = 30.0,
    ) -> InboundMessage | None:
        return poll_until(
            lambda: self._poll_once(to_address=to_address, since=since),
            timeout_s=timeout_s, interval_s=_POLL_INTERVAL_S,
        )

    def _poll_once(
        self, *, to_address: str, since: datetime,
    ) -> InboundMessage | None:
        listing = self._search(to_address)
        for entry in listing:
            arrived = _parse_arrived(entry.get("Created", ""))
            if arrived is None or arrived < since:
                continue
            return self._fetch_message(entry["ID"])
        return None

    def _search(self, to_address: str) -> list[dict]:
        url = f"{self.base_url}/api/v1/search"
        try:
            with Client(timeout=_DEFAULT_TIMEOUT) as client:
                resp = client.get(url, params={"query": f"to:{to_address}"})
        except httpx.RequestError:
            return []
        if resp.status_code != 200:
            return []
        body = resp.json() or {}
        return list(body.get("messages") or [])

    def _fetch_message(self, mailpit_id: str) -> InboundMessage | None:
        url = f"{self.base_url}/api/v1/message/{mailpit_id}"
        try:
            with Client(timeout=_DEFAULT_TIMEOUT) as client:
                resp = client.get(url)
        except httpx.RequestError:
            return None
        if resp.status_code != 200:
            return None
        return _build_message(resp.json() or {})


def _parse_arrived(raw: str) -> datetime | None:
    """Mailpit emits RFC-3339 timestamps with millisecond precision.
    `fromisoformat` handles them once we normalise `Z` to `+00:00`."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_message(payload: dict) -> InboundMessage:
    from_addr = (payload.get("From") or {}).get("Address", "") or ""
    to_list = payload.get("To") or []
    to_addr = (to_list[0].get("Address", "") if to_list else "") or ""
    arrived = _parse_arrived(payload.get("Date", "")) or datetime.now(
        timezone.utc,
    )
    return InboundMessage(
        to_address=to_addr,
        from_address=from_addr,
        subject=payload.get("Subject", "") or "",
        body_text=payload.get("Text", "") or "",
        body_html=payload.get("HTML", "") or "",
        arrived_at=arrived,
        message_id=payload.get("MessageID", "") or "",
    )
