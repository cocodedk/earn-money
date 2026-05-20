# Phase 2 — Authentication scanning layer

> Spec tree: [`../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/02-authentication/`](../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/02-authentication/)
> 22 stubs (2.1–2.22). All specs enriched via GPT-5.5 (canonical `refactor/archive-v1` commit `811c469`).
> Stacks on `feat/em-backend-scope-enforcement` (Phase 1 closeout + scope-enforcement + edge-blocking detector).

## Phase summary

Phase 1 stubs are passive recon: parse, fingerprint, classify what was sent
back. Phase 2 stubs are **active**: they send POST requests to login, reset,
and registration forms; they observe behavioural differences between
controlled probes; they may trip account lockouts, send password-reset
emails, fire audit-log alerts. Every Phase 2 stub is gated by the existing
scope-enforcement layer AND by new Phase-2-specific RoE knobs.

## Slice map

5 categories of stubs (per spec `00-overview.md`):

| Slice | Stubs | Notes |
|-------|-------|-------|
| Weak login behaviour | 2.1 / 2.2 / 2.3 / 2.4 | username enumeration, weak password policy, missing lockout, weak rate limit |
| Password reset | 2.5 / 2.6 / 2.7 / 2.8 / 2.9 | predictable tokens, token reuse, weak expiry, reset poisoning, account-takeover via email change |
| MFA | 2.10 / 2.11 / 2.12 / 2.13 | bypass, missing on sensitive flows, weak recovery codes, MFA reset abuse |
| OAuth / SSO | 2.14 / 2.15 / 2.16 / 2.17 / 2.18 | redirect URI, missing state, token substitution, account-linking flaws, login CSRF |
| Registration | 2.19 / 2.20 / 2.21 / 2.22 | duplicate account confusion, email verification bypass, invitation abuse, tenant/org join abuse |

## Plan tree

```
decisions/
  safety-floor.md            — Phase-2 RoE extensions
  shared-vs-per-stub.md      — what lives in _shared/auth/
  fixture-targets.md         — DVWA / Juice Shop / WebGoat scoped identifiers

shared-infra/
  A-form-discovery.md        — auth-form HTML/JSON discovery + parsing
  B-request-shape.md         — request-shape preservation across probes
  C-normalization.md         — strip dynamic values before diffing
  D-synthetic-ids.md         — invalid-control identifier generation
  E-roe-extensions.md        — `allow_active_login_probes` etc.

tasks/
  00-slice-AUDIT.md          — Phase 2 architecture audit (operator-vetted)
  01-shared-infra.md         — implement _shared/auth/ end-to-end
  02-stub-2-1.md … 23-stub-2-22.md — one slice per stub
  24-phase-2-close.md        — closeout + spec-review summary

verification.md              — gate before merging Phase 2
merge-gate.md                — squash-merge criteria for the stack
rollback.md                  — kill-switch + per-program freeze pathway
```

## Hard rules carried from CLAUDE.md

* **Scope is gospel** — every Phase 2 probe routes through `@guarded_runner`
  (or `guard()` directly) before any HTTP. Confirmed via slice G.
* **Two human gates** — Phase 2 findings still go to `_queue/` for manual
  promotion; the runner never auto-promotes.
* **Three-tier policy** — `rate-limited-OK` permits Phase 2; `manual-only`
  refuses (already enforced at preflight); `ambiguous` permits passive
  fingerprinting (stub 2.1's auth-form discovery is passive, but the
  controlled-probe step requires `rate-limited-OK`).
* **Per-program RoE** — Phase 2 adds three RoE knobs:
  `allow_active_login_probes`, `allow_password_reset_probes`,
  `allow_oauth_probes`. **Default FALSE** for all three. Phase 2 stubs
  refuse to send any active request unless the program's `roe.md`
  explicitly enables the relevant knob.
* **Synthetic identifiers only** — every invalid-control identifier is
  generated per scan from `example.invalid` (emails) or `scanner_invalid_*`
  (usernames). No scraping. No customer lists.
* **PII** — every auth-flow probe runs against fixture targets first;
  real-program runs require fixture-validated stubs PLUS explicit
  operator-tracked authorisation per program.

## Sequencing

1. **Plan tree drafted** (this commit).
2. **plan-tree-pipeline hardening** — codex xhigh validates the whole
   tree before any code lands.
3. **Slice 01 (shared infra)** — TDD-built `apps/stubs/_shared/auth/`
   primitives. NO stubs registered yet.
4. **Stub 2.1** as canary: implements + tests the slice-01 primitives
   in anger. Stub-done + spec-review + /simplify before moving on.
5. **Stubs 2.2 → 2.22** — iterate one stub per slice, reusing the
   slice-01 infra. Each stub stacks its own branch on the tip.
6. **Phase 2 closeout** — spec-review across all 22 stubs +
   live smoke against authorised fixtures (juiceshop.cocode.dk,
   dvwa.cocode.dk, webgoat.cocode.dk).

## Cross-tier contract impact (em-frontend)

Phase 2 introduces three new event types and one new Finding category set.
Each lands behind a feature flag so em-frontend can pick them up at their
own pace:

* `EventType.AUTH_PROBE_REFUSED` — RoE blocked an active probe.
* `EventType.AUTH_FINDING_CANDIDATE` — Finding emitted with status=candidate.
* `EventType.AUTH_FIXTURE_REQUIRED` — stub refused live target because no
  fixture-validated invocation exists yet.
* `Finding.category` values: `auth_username_enum`, `auth_weak_password`,
  `auth_missing_lockout`, `auth_weak_ratelimit`, `auth_predictable_reset_token`,
  ... (one per stub).

em-frontend gets a heads-up ping at the start of slice 01 (when the
EventType + Finding-category names land), at slice canary done (2.1), and
again at phase closeout.

## Open questions (to settle before slice 01)

1. **Fixture target prep** — DVWA + WebGoat have known auth flows; do
   they currently expose endpoints that map cleanly to the spec's auth-form
   discovery heuristics? Probably yes (DVWA's `/login.php`, WebGoat's
   `/login`), but worth confirming with a one-shot probe.
2. **Identifier scope** — `roe.md` needs an `authorized_test_accounts`
   field per program. Algolia's roe says `[]`. For Phase 2 we add fixture
   accounts to the **fixture** programs (`programs/local/juice-shop`, etc.),
   NOT to live HackerOne programs.
3. **Headless browser** — auth-form rendering on SPAs (algolia.com is one)
   needs JS execution. Phase 2 MVP stays text-only; deferred to Phase 3.
   Stubs surface a `requires_js_rendering=true` reason instead of a finding
   for SPA-heavy targets.
