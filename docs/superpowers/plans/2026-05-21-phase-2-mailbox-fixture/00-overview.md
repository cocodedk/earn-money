# Mailbox-fixture infrastructure for Phase 2

> Stacks on `feat/em-backend-phase-2`. Unblocks 7 Phase 2 stubs that
> need to read a real email the target just sent.

## Why this exists

Six password-reset stubs (2.5 – 2.9) and one registration stub (2.20)
all need the same thing: ask the target to email a token to a
scanner-owned address, then read that email to extract the token.

Some targets don't email at all — they let you log in immediately
after registration. The mailbox layer needs to handle that case too,
not just refuse-as-fixture-required.

## Three backends

The mailbox is a **plugin point**, not a single implementation. The
runner reads `FIXTURE_MAILBOX_BACKEND` env var to decide which to
use:

| Backend | What it is | When to use it |
|---------|------------|----------------|
| `imap` | Real IMAP server (Gmail app password, or any IMAP host) | Self-hosted; cheapest |
| `mailosaur` | [Mailosaur](https://mailosaur.com/) API. Per-test inboxes, REST polling | Quickest to set up; paid (~$10/mo) |
| `catchall` | Postfix on h1.cocode.dk catching `*@scanner-fixture.cocode.dk` + thin HTTP shim | Self-hosted, fully under our control |
| `none` | Target doesn't email — registration leads straight to login | Some intentionally-vulnerable apps (DVWA), trial-and-error setups |

All four expose the same `MailboxBackend` Protocol. Stubs call
`mailbox.wait_for_email_to(address, since=..., timeout=...)` and
get back a parsed message — or `None` if the backend is `none`
mode, which is a separate code path inside the stub.

## What this is NOT

* Not a permanent mailbox for human use. Every read is for one
  scanner probe.
* Not an SMTP outbound path. Targets send TO our addresses; we
  never send.
* Not LLM-driven. Token extraction is regex on the message body.
  Deterministic. Re-runnable. Auditable.

## Plan tree

```
decisions/
  backend-choice.md      — when to pick IMAP / Mailosaur / catchall / none
  address-aliasing.md    — per-fixture unique addresses; no collisions

shared-infra/
  A-mailbox-protocol.md  — MailboxBackend Protocol + helper return types
  B-imap-backend.md      — IMAP impl spec
  C-mailosaur-backend.md — Mailosaur impl spec
  D-catchall-backend.md  — Postfix sink + HTTP shim on h1
  E-no-mail-mode.md      — registration-without-email path

tasks/
  01-protocol-stub.md    — Protocol + FakeMailbox + tests
  02-imap-impl.md        — IMAPMailbox + tests
  03-canary-stub-2-5.md  — first real use: stub 2.5 (predictable reset token)
  04-catchall-h1-setup.md — operator-action: Postfix + shim on h1
```

## Stub coverage (sequencing)

1. **Slice 01** ships the Protocol + a `FakeMailbox` for tests. No
   real backend yet; tests pass against the fake.
2. **Slice 02** ships the IMAP backend — works against any
   real-world IMAP host, including Gmail with an app password.
3. **Slice 03** wires stub 2.5 (predictable-reset-token) as the
   first real fixture canary. Same TDD pattern as stub 2.1.
4. **Slice 04** (operator-action) sets up the catch-all on h1 for
   self-hosted mode.
5. **Per stub**: 2.6 → 2.7 → 2.8 → 2.9 → 2.20 follow. Each is
   ~150 LoC of stub-specific logic + shared mailbox + shared infra.

## Out of scope

* Trial-and-error fixture wiring per target. That's operator-action
  work documented in `decisions/address-aliasing.md` (which alias
  goes to which fixture).
* Mailosaur backend implementation. Spec'd but not built unless
  the operator chooses to subscribe.
* SMTP outbound. Not needed by any Phase 2 stub.
