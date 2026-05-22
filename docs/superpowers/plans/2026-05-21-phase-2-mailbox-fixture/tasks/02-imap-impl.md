# Slice 02 — IMAPMailbox backend

> Depends on slice 01. Adds the real IMAP backend so a Gmail
> app-password or any IMAP host can drive the mailbox.

## Files

* `backend/apps/stubs/_shared/auth/_imap.py` — `IMAPMailbox` class
  implementing the `MailboxBackend` Protocol.
* `backend/apps/stubs/_shared/auth/tests/test_imap.py` — tests
  against an in-memory fake IMAP server (no real network).
* `backend/apps/stubs/_shared/auth/mailbox.py` — extend
  `load_mailbox_backend()` to return `IMAPMailbox(...)` when
  `FIXTURE_MAILBOX_BACKEND=imap`.

## Implementation notes

* Use `imaplib` from stdlib for the connection (battle-tested,
  zero new deps).
* Use `email` from stdlib to parse the fetched bytes into
  `InboundMessage`.
* New connection per `wait_for_message` call (don't hold the
  socket open between probes — flaky against bot-detection).
* TLS only (port 993). Port 143 raises `MailboxConfigError`.
* Polling: 2.5 s between `SEARCH` cycles, up to `timeout_s`.

## Tests

* `wait_for_message` returns the first message matching `to` +
  `since`.
* Older messages are filtered out by `since`.
* Timeout returns None.
* MIME multipart decode (text/plain + text/html).
* Quoted-printable encoding decoded.
* `IMAPMailbox(port=143)` raises `MailboxConfigError`.
* Bad credentials (mock `imaplib.IMAP4.error`) raises
  `MailboxConfigError`.
* `extract_reset_token` on a sample real Juice Shop reset email
  body (fixture file, redacted token).

## Smoke (not in CI)

`scripts/smoke_mailbox.py` connects to the real IMAP host using
`.env` credentials and prints the latest message. Operator runs
this once at fixture-setup time to confirm the wiring.

## Commit

`feat(stubs): IMAPMailbox backend + smoke script`
