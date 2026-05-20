# Decision — address aliasing per fixture

> Each fixture target gets its own unique scanner-owned email
> address. No two fixtures share an inbox. Operator owns the
> alias-to-fixture mapping.

## Why aliasing matters

Stub 2.5 registers an account with `target=juiceshop.cocode.dk`
and triggers a password reset. The email lands. The stub then
needs to read THAT email, not a stale reset email from a previous
scan against `dvwa.cocode.dk`. Without per-fixture aliasing, the
two streams collide.

## Pattern

Per fixture program, store the address in `roe.md`:

```yaml
authorized_test_accounts:
  - "scanner-juiceshop-1@scanner-fixture.cocode.dk"
```

For each new probe, the mailbox helper polls JUST that address.
Other fixtures' messages are out of scope.

## Per-probe sub-aliasing (optional, recommended)

Some mail providers (Mailosaur, plus-addressing on Gmail) support
sub-addressing on the fly. A single probe can claim a unique
sub-address derived from the scan-run ID:

* Gmail: `scanner-juiceshop-1+<scan_run_id>@gmail.com` → same
  inbox, but the `To:` header carries the sub-address.
* Mailosaur: each test calls `create_inbox()` and gets a fresh
  address with no setup.
* Self-hosted catchall: any address ending in
  `@scanner-fixture.cocode.dk` falls into the sink, then the
  helper filters by `To:` header.
* IMAP without sub-addressing support: helper filters by
  `Date:` header + a probe-issue timestamp recorded before the
  reset request fires.

The stub passes the per-probe alias explicitly to the helper:
`wait_for_email_to(alias, since=ts, timeout=30)`. The helper
returns the first message that matches.

## Collision-safety guarantees

* Two parallel scan-runs against the same fixture must NOT race.
  Each probe gets a unique sub-alias (or, fallback, the helper
  uses `since=` to prove the message arrived AFTER the probe
  fired).
* A stale message from a previous run must NOT match. The
  `since` cutoff is the wall-clock time the probe was issued —
  the helper drops any older message.

## What the operator does

For each fixture target (DVWA / Juice Shop / WebGoat, plus any
HackerOne program where active probing is later authorised):

1. Pick a base scanner-owned address that the target's email
   verification will accept.
2. Register one canary account using that address.
3. Add the address to the fixture's `roe.md::authorized_test_accounts`.
4. Record the password in `.env` (`FIXTURE_TEST_PASSWORD_<slug>=`
   or a per-fixture variant).

The stub code never sees real user data. The only credentials
are scanner-owned.
