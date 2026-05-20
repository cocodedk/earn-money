# Slice template — one Phase 2 stub (2.2 through 2.22)

> Each stub gets its own task file `tasks/03-stub-2-N-<slug>.md`,
> created by copying this template and filling in the slots.
> Use slice 02 (stub 2.1) as the worked reference.

## Slots

* `STUB_SLUG` — e.g. `2.2`.
* `SHORT_NAME` — e.g. `weak-password-policy`.
* `SPEC_PATH` — `../../../specs/.../02-authentication/02-weak-password-policy.md`.
* `ROE_KNOB` — which of the 5 knobs gates this stub.
* `CATEGORY` — `auth_weak_password` etc.
* `DEPENDS_ON` — every other stub or shared-infra slice this stub needs.

## Required sections in the per-stub file

### Scope
What the stub looks for + how it's deterministic.

### Detection logic
Bulletised from the spec's §Detection logic. Don't rewrite — point at
the spec. Note any deviations from the spec.

### Tests (strict TDD, 100% coverage)
Per-runner test list. Each Test bullet should map to one spec assertion
(positive or negative). Include the cross-stub regression test from
`apps/stubs/test_runner_guard_wiring.py` that asserts the stub respects
the scope + RoE layer.

### Live smoke target
One of: `juiceshop.cocode.dk` / `dvwa.cocode.dk` / `webgoat.cocode.dk` /
multi. The smoke transcript is appended to the per-stub spec-review.

### em-frontend ping
If the stub introduces a new Finding category or EventType beyond
what slice 01 reserved → ping. Else no ping.

### Acceptance
* Code coverage 100%.
* Spec-review report at `docs/superpowers/spec-reviews/2026-05-21-stub-<SLUG>-<SHORT_NAME>.md`.
* Live smoke passes against the chosen fixture.
* All hard-rule regressions still green (1636+ tests).

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
