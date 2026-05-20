# Slice 01 — Protocol + FakeMailbox + helpers

> First commit. Public surface for every backend. No real backend
> wired yet.

## Files

* `backend/apps/stubs/_shared/auth/mailbox.py` — public
  `MailboxBackend` Protocol, `InboundMessage` dataclass,
  `MailboxConfigError`, `load_mailbox_backend()` stub that returns
  None for `BACKEND=none` and raises for anything else (real
  backends slot in via subsequent slices).
* `backend/apps/stubs/_shared/auth/tests/test_mailbox.py` — tests
  the Protocol, the dataclass, the `none`-mode contract, and the
  token/link extraction helpers.

## What ships

* `InboundMessage` frozen dataclass.
* `MailboxBackend` Protocol.
* `MailboxConfigError` exception.
* `extract_reset_token(msg, *, url_substring="reset")`.
* `extract_link(msg, *, url_substring)`.
* `load_mailbox_backend()` returns `None` for `BACKEND=none`,
  raises `MailboxConfigError` otherwise. IMAP / Mailosaur /
  catchall branches added in slices 02-04.

## Tests (strict TDD, 100% coverage)

* `InboundMessage` frozen.
* `extract_reset_token` finds the first matching URL and pulls
  the `token` query param.
* `extract_reset_token` falls back through `token|code|t|k`.
* `extract_reset_token` returns None when no link matches.
* `extract_link` returns the first matching URL.
* `extract_link` returns None when no link matches.
* `load_mailbox_backend()` reads `FIXTURE_MAILBOX_BACKEND`:
  - missing → `MailboxConfigError`
  - `"none"` → returns None
  - `"imap"` / `"mailosaur"` / `"catchall"` → `MailboxConfigError`
    (with a clear "backend not yet implemented" message — these
    slot in via later slices).
  - any other value → `MailboxConfigError`.

## Commit

`feat(stubs): _shared/auth/mailbox protocol + extraction helpers`
