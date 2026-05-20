# Phase 2 — Authentication scanning layer — pre-implementation audit

> Plan tree: [`../plans/2026-05-21-phase-2-authentication/`](../plans/2026-05-21-phase-2-authentication/)
> Audit date: 2026-05-20
> Slice: [00-slice-AUDIT](../plans/2026-05-21-phase-2-authentication/tasks/00-slice-AUDIT.md)

## Surface inventory

Twenty-two stubs across five categories:

| Slice | Stub | Short name | Category | RoE knob | Finding.category | Fixture |
|------:|------|------------|----------|----------|------------------|---------|
| 02 | 2.1  | username-enumeration | login | `allow_active_login_probes` | `auth_username_enum` | juice-shop |
| 04 | 2.2  | weak-password-policy | login | `allow_active_login_probes` | `auth_weak_password` | juice-shop / dvwa |
| 05 | 2.3  | missing-lockout | login | `allow_active_login_probes` | `auth_missing_lockout` | juice-shop / dvwa |
| 06 | 2.4  | weak-rate-limiting | login | `allow_active_login_probes` | `auth_weak_ratelimit` | juice-shop / dvwa |
| 07 | 2.5  | predictable-reset-token | reset | `allow_password_reset_probes` | `auth_predictable_reset_token` | **fixture secret required** |
| 08 | 2.6  | reset-token-reuse | reset | `allow_password_reset_probes` | `auth_reset_token_reuse` | **fixture secret required** |
| 09 | 2.7  | weak-reset-expiry | reset | `allow_password_reset_probes` | `auth_weak_reset_expiry` | **fixture secret required** |
| 10 | 2.8  | reset-poisoning | reset | `allow_password_reset_probes` | `auth_reset_poisoning` | **fixture secret required** |
| 11 | 2.9  | email-change-takeover | reset | `allow_password_reset_probes` | `auth_email_change_takeover` | **fixture secret required** |
| 12 | 2.10 | mfa-bypass | MFA | `allow_mfa_probes` | `auth_mfa_bypass` | webgoat + MFA secret |
| 13 | 2.11 | mfa-missing-sensitive-flow | MFA | `allow_mfa_probes` | `auth_mfa_missing_sensitive_flow` | webgoat + MFA secret |
| 14 | 2.12 | weak-recovery-codes | MFA | `allow_mfa_probes` | `auth_weak_recovery_codes` | webgoat + recovery codes |
| 15 | 2.13 | mfa-reset-abuse | MFA | `allow_mfa_probes` | `auth_mfa_reset_abuse` | webgoat + MFA reset |
| 16 | 2.14 | oauth-redirect-uri | OAuth | `allow_oauth_probes` | `auth_oauth_redirect_uri` | **OAuth fixture required** |
| 17 | 2.15 | oauth-missing-state | OAuth | `allow_oauth_probes` | `auth_oauth_missing_state` | **OAuth fixture required** |
| 18 | 2.16 | oauth-token-substitution | OAuth | `allow_oauth_probes` | `auth_oauth_token_substitution` | **OAuth fixture required** |
| 19 | 2.17 | oauth-account-linking | OAuth | `allow_oauth_probes` | `auth_oauth_account_linking` | **OAuth fixture required** |
| 20 | 2.18 | login-csrf | OAuth | `allow_oauth_probes` | `auth_login_csrf` | webgoat / OAuth fixture |
| 21 | 2.19 | duplicate-account-confusion | registration | `allow_registration_probes` | `auth_duplicate_account_confusion` | juice-shop |
| 22 | 2.20 | email-verification-bypass | registration | `allow_registration_probes` | `auth_email_verification_bypass` | juice-shop + mailbox |
| 23 | 2.21 | invitation-abuse | registration | `allow_registration_probes` | `auth_invitation_abuse` | owned invitation fixture |
| 24 | 2.22 | tenant-org-join-abuse | registration | `allow_registration_probes` | `auth_tenant_org_join_abuse` | owned tenant fixture |

## Shared-vs-per-stub split

| Primitive | Lives in | Consumers |
|-----------|----------|-----------|
| Form discovery (HTML + JSON) | `_shared/auth/forms.py` | 2.1, 2.2, 2.3, 2.4, 2.5, 2.8, 2.9, 2.10, 2.18, 2.19, 2.20 |
| Probe-pair construction | `_shared/auth/requests.py` | 2.1, 2.2, 2.3, 2.4, 2.5 |
| Response normalisation + diff | `_shared/auth/normalize.py` | every comparison stub |
| Synthetic identifiers | `_shared/auth/identifiers.py` | every stub that submits identifiers |
| Candidate paths | `_shared/auth/endpoints.py` | every stub that bounded-probes |
| Active-safety helper | `_shared/auth/safety.py` | every active Phase 2 stub |

Per-stub: `signatures.py` (per-stub patterns), `classify.py` (verdict mapping), `runner.py` (registration + glue).

## Cross-tier contract table (em-frontend)

| Symbol | Defined in | Slice landing |
|--------|------------|---------------|
| `EventType.AUTH_PROBE_REFUSED` | `apps.events.types` | 01 (reserved); first emit 02 |
| `EventType.AUTH_FINDING_CANDIDATE` | `apps.events.types` | 01 (reserved); first emit 02 |
| `EventType.AUTH_FIXTURE_REQUIRED` | `apps.events.types` | 01 (reserved); first emit per fixture-gated stub |
| `Finding.category="auth_username_enum"` | new value | 02 |
| `Finding.category="auth_*"` (21 more) | new values | 04-24 (one per stub) |

em-frontend pinged at slice 01 close + each contract-impacting stub.

## Hard-rule traceability

| CLAUDE.md hard rule | Phase 2 enforcement point |
|---------------------|---------------------------|
| Scope is gospel | `@guarded_runner` (reused from Phase 1 slice G) |
| Three-tier policy | `_enforce_policy` (preflight, reused from scope-enforcement slice D) |
| RECON_ENABLED kill-switch | `require_recon_enabled` inside `guard()` |
| Per-program FROZEN | `is_program_frozen` inside `guard()` |
| Wildcards don't match apex | `apps.programs.scope.matches_any` (unchanged) |
| Negative-scope-is-gospel | `enforce_scope` checks `out_of_scope` first (unchanged) |
| Per-program RoE | new 5 knobs on `RoE` + per-stub gate at top of `run()` |
| Per-program rate-limit | `acquire_for(program)` + per-HTTP application (slice H follow-up #1, **prerequisite for slice 01**) |
| Two human gates | unchanged — `auth_*` Findings still go to `_queue/` |
| GDPR Art. 28 PII | synthetic identifiers + fixture-only credential probing |

## Answers to slice-00 open questions

1. **Does `algolia/roe.md` need the 5 new knobs *now*?**
   Yes — default-deny must be visible so the operator can SEE what
   they're authorising. Slice 01 ships the schema; operator manually
   adds the knobs to existing program roe.md files.

2. **Per-HTTP rate-limit gap from slice F?**
   Lands in slice 01 (prerequisite for any Phase 2 probe). Acknowledged
   open issue; no Phase 2 stub fires HTTP until this is in place.

3. **Minimum fixture scope for slice 02?**
   `programs/local/juice-shop` with one scoped test account. If Juice
   Shop login discovery does not pass, slice 02 blocks rather than
   falling back to a live H1 program.

4. **Headless rendering?**
   Emit `AUTH_FIXTURE_REQUIRED` with `reason="requires_js_rendering"`.
   Phase 3 work.

5. **Stubs lacking owned-fixture prerequisites?**
   2.5-2.9 (reset flows) need a mailbox sink. 2.14-2.17 (OAuth) need an
   OAuth client fixture. 2.10-2.13 (MFA) need WebGoat MFA seed data
   plus recovery codes. 2.21-2.22 need owned tenant/invitation fixtures.
   These stubs block on fixture setup before implementation.

## Blocks slice 01 if

* The per-HTTP rate-limit fix from scope-enforcement slice H is missing
  on the base branch. (Verify: `acquire_for` is called per HTTP not per
  runner-invocation.)
* `programs/local/juice-shop/` is not scoped with
  `allow_active_login_probes: true`. (Verify: presence of fixture
  scope.md + roe.md before slice 02 starts.)
* Any of the three new EventTypes is misnamed. (Verify against the
  contract table above.)
* Any fixture secret required by slice 02 is not yet named in
  `programs/local/juice-shop/roe.md` (e.g. `FIXTURE_TEST_PASSWORD` env
  var). (Verify before slice 02 starts.)

## Verdict

Phase 2 plan tree is READY. Slice 01 may begin once the per-HTTP
rate-limit prerequisite is verified in place on the base branch.
