# Decision — Shared `_shared/auth/` vs per-stub code

> Status: proposed.

## Rule of thumb

Code lives in `apps/stubs/_shared/auth/` if and only if:

* Two or more Phase 2 stubs need it; OR
* It enforces a hard rule from CLAUDE.md (synthetic identifiers,
  scope check, normalisation invariants) and any drift between
  stubs would be a safety regression.

Everything else lives in the stub's own package.

## Concrete map

| Concern | Lives in | Used by |
|---------|----------|---------|
| Auth-form discovery (HTML + JSON) | `_shared/auth/forms.py` | 2.1 / 2.2 / 2.3 / 2.4 / 2.5 / 2.8 / 2.9 / 2.10 / 2.18 / 2.19 / 2.20 |
| Probe-pair construction | `_shared/auth/requests.py` | 2.1 / 2.2 / 2.3 / 2.4 / 2.5 |
| Response normalisation + diff | `_shared/auth/normalize.py` | every comparison stub |
| Synthetic identifier generation | `_shared/auth/identifiers.py` | every stub that submits identifiers |
| Candidate login/reset/register paths | `_shared/auth/endpoints.py` | every stub that bounded-probes |
| Token entropy + Wiener attack | `apps/stubs/predictable_reset_tokens/` | 2.5 only |
| OAuth state-param parsing | `apps/stubs/oauth_state_missing/` | 2.15 only |
| MFA bypass heuristics | `apps/stubs/mfa_bypass/` | 2.10 only |
| Email-change confirmation flow | `apps/stubs/email_change_takeover/` | 2.9 only |

## What does NOT live in `_shared/auth/`

* Per-stub `signatures.py` — stub-specific patterns (e.g. JSON error
  codes for reset-token reuse) stay local.
* Per-stub `classify.py` — verdict mapping from spec table to
  Finding status / confidence.
* Per-stub `runner.py` — registers `@guarded_runner("2.N")` and wires
  the shared helpers together.

## Why this matters

If every stub copies the form discoverer + normaliser into its own
module, 22 forks of the same logic emerge. The first time someone
edits the cookie-stripping pattern in `_shared/auth/normalize.py` to
handle a new framework's session cookie, ALL 22 stubs benefit.
Without sharing, only one does, and the next 21 silently emit false
positives until each is patched.

## Test policy

`_shared/auth/*` modules carry their own test files at 100% coverage.
Per-stub tests don't re-test shared primitives — they test the
*stub's specific logic* against mocked-or-real shared primitives.
