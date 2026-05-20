# Slice 00 — Phase 2 architecture audit

> Pre-implementation audit. Runs before slice 01. Operator-vetted before
> any code lands. Output committed at
> `docs/superpowers/spec-reviews/2026-05-21-phase-2-authentication-pre.md`.

## Goal

Three deliverables in one short document:

1. **Surface inventory.** What auth-flow surface area do the 22 Phase 2
   stubs cover? Map every stub to its category (login / reset / MFA /
   OAuth / registration) and the shared primitives it needs.

2. **Shared-vs-per-stub split.** For each shared-infra primitive (A–E in
   `../shared-infra/`), list which stubs consume it. Anything used by
   ≥2 stubs lives in `_shared/auth/`. Single-stub helpers stay in the
   stub's own module.

3. **Hard-rule traceability.** For every CLAUDE.md hard rule, identify
   the Phase 2 enforcement point. Match scope-enforcement's slice-H
   audit pattern: a table mapping `rule → production code path → test`.

## Specific questions to answer

* Does `algolia/roe.md` need the 5 new knobs *now*, or only when an
  operator chooses to enable active probing? **Now** (default-deny
  must be visible in every program's roe.md so the operator can SEE
  what they're authorising).
* Does the existing `acquire_for(program)` rate-limit budget cover
  Phase 2's per-HTTP needs, or do we need a per-probe-pair budget?
  Answer: per-HTTP fix from slice F's followup must land in slice 01.
* What's the minimum fixture-target scope for slice 02 (stub 2.1
  canary)? Likely `programs/local/juice-shop` with one scoped test
  account. WebGoat + DVWA targets land per-stub as needed.
* Headless rendering: do we punt on SPAs entirely or emit a
  `requires_js_rendering` event? Answer: emit the event, defer to
  Phase 3.

## Output format

The audit doc is a one-pager (≤200 lines), structured exactly like
`docs/superpowers/spec-reviews/2026-05-21-scope-enforcement-pre.md`.
No code. Just clarifying questions answered, decisions recorded,
and the slice-01 enabling list.

## Commit

`docs(spec-reviews): Phase 2 architecture audit (pre-impl)`
