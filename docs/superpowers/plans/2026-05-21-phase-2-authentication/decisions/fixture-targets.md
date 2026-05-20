# Decision — Fixture targets for Phase 2

> Status: proposed.

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

## Per-fixture roe.md

Each fixture becomes a registered Program at
`programs/local/<slug>/scope.md` + `roe.md`:

| Fixture | Stubs likely to fire |
|---------|----------------------|
| juice-shop | 2.1 / 2.2 / 2.3 / 2.4 / 2.19 / 2.20 |
| dvwa       | 2.1 / 2.2 / 2.3 / 2.4 (text-based) |
| webgoat    | 2.1 / 2.10 / 2.11 / 2.12 / 2.13 / 2.18 (MFA + CSRF) |

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

## What this enables

* Every Phase 2 stub can demo end-to-end without touching a live H1
  program.
* The smoke-from-h1 path that worked for Phase 1's algolia probe
  works for Phase 2's fixtures too — `scan-on-vps.sh
  https://juiceshop.cocode.dk/ 2.1` will run.
* Live HackerOne programs stay passive-only (Phase 1) until the
  operator explicitly opts in via `roe.md`.

## Open thread (operator-vetoed)

* The three local fixtures are NOT publicly indexed. They're
  reachable from the open internet but Caddy on `target.cocode.dk`
  doesn't advertise them. Phase 2 scans against them DO emit
  traffic that DigitalOcean / Hetzner billing can see — operator
  treats them as authorised egress.
