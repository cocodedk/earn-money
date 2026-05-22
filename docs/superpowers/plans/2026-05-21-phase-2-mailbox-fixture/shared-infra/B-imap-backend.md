# Slice B — IMAPMailbox backend

> Lives in `backend/apps/stubs/_shared/auth/_imap.py` (underscore-
> prefixed because it's not part of the public mailbox API).
> Implemented in slice 02.

## Surface

```python
class IMAPMailbox:
    def __init__(
        self, *, host: str, port: int = 993,
        user: str, password: str,
        idle: bool = False,
    ) -> None: ...

    def wait_for_message(self, to_address, *, since, timeout_s=30.0):
        """Connect → SELECT INBOX → SEARCH for messages addressed
        to ``to_address`` AND newer than ``since`` → return the
        first match, decoded into an `InboundMessage`. On timeout
        returns None."""
```

## Poll behaviour

* IMAP `SEARCH` polled every 2.5 s for up to `timeout_s`.
* Search criteria: `TO "<to_address>" SINCE <DD-MMM-YYYY>`.
  IMAP's `SINCE` resolves to date, not timestamp; the helper
  filters by `received-date` on the Python side for sub-day
  precision.
* `IDLE` mode (RFC 2177) is supported but disabled by default —
  some providers (Gmail) misbehave on long-lived IDLE from a
  scanner. The 2.5 s poll is cheap enough.

## MIME decoding

* Prefer `text/plain` over `text/html` for `body_text`. Both are
  exposed.
* Quoted-printable + base64 transfer encodings decoded transparently.
* HTML body NOT sanitized — the stub never renders it; it only
  extracts URLs / tokens.
* Address fields parsed via `email.utils.parseaddr` so display
  names don't leak into `to_address`.

## Connection hygiene

* New connection per `wait_for_message` call. Long-lived IMAP
  sockets are flaky against bot-detection.
* TLS only (port 993 default). Plain port 143 IMAP is refused —
  setting `port=143` raises `MailboxConfigError`.
* App-password auth only (Gmail-specific note: regular passwords
  fail with "Application-specific password required" — operator
  must generate an app-password).

## Tests (slice 02)

* Mock-based: a fake IMAP server returns scripted `LIST` /
  `SEARCH` / `FETCH` responses.
* Search-by-recipient-and-since logic.
* MIME-multipart decoding (text/plain + text/html).
* Quoted-printable decoding.
* Timeout returns None.
* Bad-credentials raises `MailboxConfigError` (NOT a network
  error — explicit type so the runner surfaces it as a fixture
  problem, not a target-side issue).
* `port=143` raises `MailboxConfigError` at construction.

## Tests do NOT hit a real IMAP server

The IMAP backend is exercised against an in-memory fake during
unit tests. Operator runs `scripts/smoke_mailbox.py` once with
real credentials to confirm the wiring at fixture-setup time;
that's documented in slice 04 (operator-action), not unit-tested
in CI.
