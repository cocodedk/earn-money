# Decision — Fixture targets for Phase 2

> Status: ready for slice 00 audit.

## Problem

Phase 2 stubs submit forms. Submitting forms against live HackerOne
programs has real-world consequences (lockouts, audit alerts,
unsolicited emails). The first wall against operator pain is to
develop and test stubs against **fixture targets** — known-vulnerable
applications the operator OWNS.

CLAUDE.md authorises four HTTPS endpoints:

* `https://target.cocode.dk/` — Juice Shop (mystery, no hostname leak).
* `https://juiceshop.cocode.dk/` — Juice Shop (identifiable).
* `https://dvwa.cocode.dk/` — DVWA, default creds `admin`/`password`.
* `https://webgoat.cocode.dk/` — WebGoat, self-registration.

All four allow "any HTTP technique". Phase 2's fixture work runs there.
`target.cocode.dk` is treated as an alias of Juice Shop for smoke coverage,
not a separate `programs/local/<slug>` entry, unless slice 00 discovers that
its scope or auth surface differs from `juiceshop.cocode.dk`.

## Per-fixture roe.md

Each fixture becomes a registered Program at
`programs/local/<slug>/scope.md` + `roe.md`:

| Fixture | Stubs likely to fire |
|---------|----------------------|
| juice-shop | 2.1 / 2.2 / 2.3 / 2.4 / 2.19 / 2.20 |
| dvwa       | 2.1 / 2.2 / 2.3 / 2.4 (text-based) |
| webgoat    | 2.1 / 2.10 / 2.11 / 2.12 / 2.13 / 2.18 (MFA + CSRF) |

Password-reset and OAuth/SSO stubs are fixture-gated until slice 00 or the
per-stub task records a concrete owned flow:

| Surface | Fixture requirement before active testing |
|---------|-------------------------------------------|
| Password reset (2.5-2.9) | operator-owned mailbox/sink or fixture API that exposes reset tokens |
| OAuth / SSO (2.14-2.18) | fixture OAuth client/provider config with owned redirect URIs |
| Invitations / tenant joins (2.21-2.22) | owned fixture tenant/org and disposable invitation codes |

Each fixture's `roe.md` sets:

```yaml
max_requests_per_second: 30      # fixtures can handle more burst
allow_active_login_probes: true
allow_password_reset_probes: true
allow_mfa_probes: true
allow_oauth_probes: true
allow_registration_probes: true
authorized_test_accounts:
  - "scanner-fixture-1"
  - "scanner-fixture-2@example.invalid"
```

The `scope.md` for each fixture pins the host:

```yaml
platform: local
slug: juice-shop
policy: rate-limited-OK
in_scope:
  - juiceshop.cocode.dk
out_of_scope: []
```

## Test account provisioning

`scanner-fixture-1` is pre-registered on each fixture by hand (one
operator action per fixture). The test account password is stored in
the local `.env` under `FIXTURE_TEST_PASSWORD` and read by stubs that
need a `valid_identifier` for the comparison oracle. NEVER committed.

If a stub needs a second account, mailbox sink, OAuth client secret, MFA
recovery code, invitation code, or tenant/org identifier, the per-stub task
must name the exact secret variable it expects and the fixture setup step that
creates it. Missing fixture secrets block the stub with `AUTH_FIXTURE_REQUIRED`;
they never fall back to live HackerOne targets.

## What this enables

* Every Phase 2 stub can demo end-to-end without touching a live H1
  program.
* The smoke-from-h1 path that worked for Phase 1's algolia probe
  works for Phase 2's fixtures too — `scan-on-vps.sh
  https://juiceshop.cocode.dk/ 2.1` will run.
* Live HackerOne programs stay passive-only (Phase 1) until the
  operator explicitly opts in via `roe.md`.

## Recorded operator decision

* The three local fixtures are NOT publicly indexed. They're
  reachable from the open internet but Caddy on `target.cocode.dk`
  doesn't advertise them. Phase 2 scans against them DO emit
  traffic that DigitalOcean / Hetzner billing can see — operator
  treats them as authorised egress.
