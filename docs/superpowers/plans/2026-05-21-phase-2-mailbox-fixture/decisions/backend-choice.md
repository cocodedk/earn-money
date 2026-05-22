# Decision — which mailbox backend, when

> Status: proposed.

## Rule

`FIXTURE_MAILBOX_BACKEND` env var picks one. Multiple backends can
coexist if different programs use different ones (per-program env
override via `programs/<platform>/<slug>/roe.md::mailbox_backend`,
optional Phase 3).

## When to pick each

### `imap` — default for self-hosted

Pros: zero new infrastructure if you already have a domain with
email. Works against any IMAP host: Gmail-with-app-password,
ProtonMail Bridge, Fastmail, self-hosted Dovecot.

Cons: rate-limited by the provider; Gmail in particular treats
sustained bot polling as abusive. Latency: 5-30 s between
sending and IMAP-visible.

Required env:
* `FIXTURE_MAILBOX_BACKEND=imap`
* `FIXTURE_MAILBOX_IMAP_HOST` (e.g. `imap.gmail.com`)
* `FIXTURE_MAILBOX_IMAP_PORT` (default `993`)
* `FIXTURE_MAILBOX_IMAP_USER` (full email address)
* `FIXTURE_MAILBOX_IMAP_PASSWORD` (Gmail: app password, NOT account password)

### `mailosaur` — paid, fastest to set up

Pros: per-test inboxes, sub-second delivery, no rate limits, API
explicitly designed for this use case. Inboxes auto-delete.

Cons: $9/mo as of 2026. External SaaS dependency.

Required env:
* `FIXTURE_MAILBOX_BACKEND=mailosaur`
* `FIXTURE_MAILBOX_MAILOSAUR_API_KEY`
* `FIXTURE_MAILBOX_MAILOSAUR_SERVER_ID` (their per-account namespace)

### `catchall` — self-hosted on h1.cocode.dk

Pros: under our control. Free. Scales to any number of
per-fixture aliases. No external dependency.

Cons: needs Postfix + a tiny HTTP shim on h1 (operator-action,
spec'd in `shared-infra/D-catchall-backend.md`).

Required env:
* `FIXTURE_MAILBOX_BACKEND=catchall`
* `FIXTURE_MAILBOX_CATCHALL_URL` (e.g. `https://h1.cocode.dk/mailsink/`)
* `FIXTURE_MAILBOX_CATCHALL_TOKEN` (API token)

### `none` — target doesn't send email

Some intentionally-vulnerable apps (DVWA, some lab fixtures)
register-and-login with no email step. The stub still uses
`FIXTURE_MAILBOX_BACKEND=none` to declare this explicitly, so
the runner doesn't wait for an email that will never arrive.

The stub then enters its `no_mailbox_mode` branch (spec
`E-no-mail-mode.md`): immediately attempts to log in with the
registered credentials. If login succeeds without email
verification, that IS the finding for stub 2.20
(email-verification-bypass). For 2.5-2.9, `none` mode means
the stub returns `STALE / low` because there's no way to test
the reset chain.

## Trial-and-error path

The user observed: "some targets don't send an answer back, they
just register and you can login afterwards". The operator's
fixture-onboarding playbook:

1. Try to register manually on the target with a scanner-owned
   email.
2. If email arrives → `imap` / `mailosaur` / `catchall` mode.
3. If no email arrives and you can still log in → `none` mode.
4. If no email AND can't log in → target needs human approval
   (e.g. invite-only), out of Phase 2 scope.

The runner doesn't infer the mode automatically. The operator
declares it per fixture via `FIXTURE_MAILBOX_BACKEND` plus any
backend-specific config.

## Default for Phase 2 canary work

Start with `imap` against a dedicated Gmail account on the
scanner's own domain. Cheapest to validate the protocol; switch
to Mailosaur or catchall once the IMAP rate-limit becomes a
problem.
