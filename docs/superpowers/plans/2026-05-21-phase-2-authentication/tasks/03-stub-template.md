# Slice template — one Phase 2 stub (2.2 through 2.22)

> Each stub gets its own task file `tasks/<NN>-stub-2-N-<slug>.md`
> (slice numbers start at 04 and increment monotonically through 24,
> per the plan-tree diagram in `00-overview.md`). Copy this template,
> rename to the next free `<NN>`, and fill in the slots.
> Use slice 02 (stub 2.1) as the worked reference.

## Slots

* `STUB_SLUG` — e.g. `2.2`.
* `SHORT_NAME` — e.g. `weak-password-policy`.
* `SPEC_PATH` — `../../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/02-authentication/<NN>-<short-name>.md`.
* `ROE_KNOB` — which of the 5 knobs gates this stub.
* `CATEGORY` — `auth_weak_password` etc.
* `DEPENDS_ON` — every other stub or shared-infra slice this stub needs.
* `FIXTURE` — owned fixture host and any required secret/mailbox/client setup.

## Canonical stub roster

| Slice | Stub | Short name | RoE knob | Category | Fixture default |
|-------|------|------------|----------|----------|-----------------|
| 04 | 2.2 | weak-password-policy | `allow_active_login_probes` | `auth_weak_password` | juice-shop / dvwa |
| 05 | 2.3 | missing-lockout | `allow_active_login_probes` | `auth_missing_lockout` | juice-shop / dvwa |
| 06 | 2.4 | weak-rate-limiting | `allow_active_login_probes` | `auth_weak_ratelimit` | juice-shop / dvwa |
| 07 | 2.5 | predictable-reset-token | `allow_password_reset_probes` | `auth_predictable_reset_token` | mailbox fixture required |
| 08 | 2.6 | reset-token-reuse | `allow_password_reset_probes` | `auth_reset_token_reuse` | mailbox fixture required |
| 09 | 2.7 | weak-reset-expiry | `allow_password_reset_probes` | `auth_weak_reset_expiry` | mailbox fixture required |
| 10 | 2.8 | reset-poisoning | `allow_password_reset_probes` | `auth_reset_poisoning` | mailbox fixture required |
| 11 | 2.9 | email-change-takeover | `allow_password_reset_probes` | `auth_email_change_takeover` | mailbox fixture required |
| 12 | 2.10 | mfa-bypass | `allow_mfa_probes` | `auth_mfa_bypass` | webgoat + MFA secret |
| 13 | 2.11 | mfa-missing-sensitive-flow | `allow_mfa_probes` | `auth_mfa_missing_sensitive_flow` | webgoat + MFA secret |
| 14 | 2.12 | weak-recovery-codes | `allow_mfa_probes` | `auth_weak_recovery_codes` | webgoat + recovery codes |
| 15 | 2.13 | mfa-reset-abuse | `allow_mfa_probes` | `auth_mfa_reset_abuse` | webgoat + MFA reset flow |
| 16 | 2.14 | oauth-redirect-uri | `allow_oauth_probes` | `auth_oauth_redirect_uri` | OAuth fixture required |
| 17 | 2.15 | oauth-missing-state | `allow_oauth_probes` | `auth_oauth_missing_state` | OAuth fixture required |
| 18 | 2.16 | oauth-token-substitution | `allow_oauth_probes` | `auth_oauth_token_substitution` | OAuth fixture required |
| 19 | 2.17 | oauth-account-linking | `allow_oauth_probes` | `auth_oauth_account_linking` | OAuth fixture required |
| 20 | 2.18 | login-csrf | `allow_oauth_probes` | `auth_login_csrf` | webgoat / OAuth fixture |
| 21 | 2.19 | duplicate-account-confusion | `allow_registration_probes` | `auth_duplicate_account_confusion` | juice-shop |
| 22 | 2.20 | email-verification-bypass | `allow_registration_probes` | `auth_email_verification_bypass` | juice-shop + mailbox fixture |
| 23 | 2.21 | invitation-abuse | `allow_registration_probes` | `auth_invitation_abuse` | owned invitation fixture |
| 24 | 2.22 | tenant-org-join-abuse | `allow_registration_probes` | `auth_tenant_org_join_abuse` | owned tenant fixture |

## Required sections in the per-stub file

### Scope
What the stub looks for + how it's deterministic.

### Detection logic
Bulletised from the spec's §Detection logic. Don't rewrite — point at
the spec. Note any deviations from the spec.

### Probe budget + abort handling
Name the `ProbeBudget`, max forms, max submits, repeat-confirmation rule,
and every abort signal that downgrades to `stale` or event-only refusal.
Unsafe `GET` credential forms and missing fixture secrets must refuse before
active submission.

### Tests (strict TDD, 100% coverage)
Per-runner test list. Each Test bullet should map to one spec assertion
(positive or negative). Include the cross-stub regression test from
`apps/stubs/test_runner_guard_wiring.py` that asserts the stub respects
the scope + RoE layer.

### Live smoke target
One of: `juiceshop.cocode.dk` / `dvwa.cocode.dk` / `webgoat.cocode.dk` /
multi / named owned fixture. The smoke transcript is appended to the per-stub
spec-review. If the roster says "fixture required", create the fixture setup
step before implementing the stub; do not substitute a live HackerOne target.

### em-frontend ping
If the stub introduces a new Finding category or EventType beyond
what slice 01 reserved → ping. Else no ping.

### Acceptance
* Code coverage 100%.
* Spec-review report at `docs/superpowers/spec-reviews/2026-05-21-stub-<SLUG>-<SHORT_NAME>.md`.
* Live smoke passes against the chosen fixture.
* All hard-rule regressions still green — no tests deleted vs base.

### Commit
`feat(stubs): <SLUG> <short-name> runner`

## Out of scope for any per-stub slice

* New shared infra. If the stub needs something not in `_shared/auth/`,
  pause and either (a) extend `_shared/auth/` in its own micro-slice, or
  (b) keep it stub-local with a follow-up issue.
* Cross-stub idempotence + stale tracking — same shared-infra gap
  noted in Phase 1 stubs (#82). Tracked separately.
* SPA / headless rendering — Phase 3.

## Stack ordering

Stubs land in spec order: 2.2 → 2.3 → ... → 2.22. Each stub stacks its
own branch on the previous tip. One squash-merge of the Phase 2 tip
lands the whole stack on `main` per
[[project-stacked-branch-convention]].
