# Decision — Phase 2 RoE safety floor

> Status: ready for slice 00 audit; operator sign-off still required for
> live-program use.

## Problem

Phase 1 was passive. Every probe is `GET` or `HEAD` against the target's
public surface. Worst case: hot log entries. Phase 2 sends `POST` requests
to login forms, reset endpoints, OAuth callbacks, and registration flows.
Worst case for a buggy stub:

* Lock a legitimate account (3 failed logins → 15-min freeze).
* Send unsolicited password-reset emails to real users.
* Burn through anti-CSRF token quotas.
* Fire SOC alerts.
* Submit to GDPR-protected fields.

The existing scope-enforcement layer + token-bucket rate limit are
**necessary but insufficient** for Phase 2 — they protect against scanning
the wrong target, not against probing the right target unsafely.

## Decision

Add five RoE knobs to `apps/programs/roe.py::RoE`, all defaulting to `False`:

| Knob | Gates |
|------|-------|
| `allow_active_login_probes` | stubs 2.1 / 2.2 / 2.3 / 2.4 (login behaviour) |
| `allow_password_reset_probes` | stubs 2.5 / 2.6 / 2.7 / 2.8 / 2.9 (reset flows) |
| `allow_oauth_probes` | stubs 2.14 / 2.15 / 2.16 / 2.17 / 2.18 (OAuth/SSO) |
| `allow_registration_probes` | stubs 2.19 / 2.20 / 2.21 / 2.22 (registration) |
| `allow_mfa_probes` | stubs 2.10 / 2.11 / 2.12 / 2.13 (MFA) |

Each Phase 2 runner reads the relevant knob in its `run()` body and emits
`AUTH_PROBE_REFUSED` (with reason="roe_disabled") instead of running.
Fixture programs (`programs/local/juice-shop`, `programs/local/dvwa`,
`programs/local/webgoat`) get all five knobs set to `True` so the stubs
can exercise their auth flows.

Add one shared active-safety helper in `_shared/auth/safety.py` (specified in
[`../shared-infra/F-active-safety.md`](../shared-infra/F-active-safety.md)).
Every Phase 2 runner must declare a per-run probe budget before it builds
requests. The helper refuses or aborts before more HTTP is sent when a stub:

* would submit credentials or identifiers via a login/register/reset `GET`
  form instead of `POST`;
* has no fixture-validated target for the stub's flow;
* sees CAPTCHA, WAF, account-lockout, MFA challenge, or rate-limit evidence;
* would exceed the stub's active-submit cap for one scan run;
* lacks the fixture credential or mailbox secret required for that flow.

## Why default `False`

The same principle that drove the original `RECON_ENABLED` flag: operator
opt-in for every active behaviour. Cookbook scanners that ship with active
probing enabled by default are how bug-bounty programs get banned from
HackerOne in 24 hours. A new program onboards at the conservative floor
and the operator explicitly raises each knob as authorisation is verified
in writing.

## What this does NOT change

* The repo-wide `RECON_ENABLED` kill switch still applies to every stub.
* The token-bucket rate limit still applies; each Phase 2 probe acquires
  per HTTP, not per runner-invocation (slice 01 fixes the per-iteration
  rate-limit gap noted in slice H of scope-enforcement).
* The scope check + FROZEN re-check still fire.
* The shared active-safety helper does not replace RoE. It is the second
  gate after RoE and before request construction/execution.

## Migration path for `algolia/roe.md`

Algolia's `roe.md` currently has:
```yaml
authorized_test_accounts: []
```
For Phase 2 to run against algolia, the operator must:
1. Negotiate fixture accounts with the program (rare on H1 — most
   programs require you to register your own).
2. Set the five `allow_*_probes` knobs explicitly.
3. Populate `authorized_test_accounts` with the negotiated identifiers.

Default-deny means algolia stays passive-only until step 2 is done.

## Credential and side-effect boundary

`authorized_test_accounts` are identifiers, not credentials. A stub that needs
a password, MFA recovery code, OAuth client, invitation code, or reset-mail
capture must read an explicitly named fixture secret and fail closed when that
secret is absent. Password-reset stubs may use `example.invalid` only for
invalid-control submissions; any test that needs to read a reset token must use
an operator-owned fixture mailbox/sink.

## Tests added by this decision

* RoE-disabled stubs emit `AUTH_PROBE_REFUSED` and make zero discovery or
  submit requests.
* Unsafe `GET` credential forms emit `AUTH_PROBE_REFUSED` with
  `reason="unsafe_method"` and make zero submits.
* CAPTCHA/WAF/lockout evidence aborts the current form and records a stale
  outcome or event, never a confirmed finding.
* Missing fixture secrets produce `AUTH_FIXTURE_REQUIRED`, not a best-effort
  live-program probe.
