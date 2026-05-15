# Plugin idea: `state-machine-fuzzer`

> Research note 2026-05-15. Pre-brainstorm. **Ambitious — defer behind cheaper plugins.**

## What

Stateful endpoint-sequence prober. Models known workflows (trip lifecycle, multi-step checkout, batch operations) as a state machine, then explores partial / out-of-order / repeated transitions and detects inconsistent terminal states. Distinct from stateless probes in that it carries session + resource-state across multiple requests.

## Why

The three Logic-Flaws in Bykea's corpus are textbook state-machine bugs:

- `hackerone/reports/2861888` — Chained `GET /v1/config?trip_id=X` (mints a hash) → forged `PUT /v1/bidding` (injects a forged bid that inflates another customer's fare). The chain breaks an authorization assumption because the hash is per-input, not per-session.
- `hackerone/reports/2894018` — Cross-trip feedback: auth'd passenger sent their own valid `trip_id` paired with any `driver_id`, leaving fake feedback for drivers they never rode with. State-machine angle: the feedback transition doesn't validate the (trip, driver) pair was an actual ride. Could alternatively be addressed by `idor-probe`'s mutation-with-paired-IDs variant — natural fit either way.
- `hackerone/reports/3295503` — Cancelling one trip inside a batch leaves the batch in an inconsistent state; assigned partner stuck between completable and cancellable.

These can't be found by stateless scanners. They need a model of "what valid sequence of operations on this resource looks like" and then attempts at invalid sequences.

## Why deferred

This is the hardest of the five plugin ideas. Three reasons:

1. **Building the state-machine model is per-target.** Bykea's trip lifecycle is one model; another program's order-checkout is a different model. The plugin is really a framework for declaring per-target state machines, plus the fuzzer that explores them. The framework is reusable; the per-target models aren't.
2. **Confidence on hits is lower.** A 200 OK on a "shouldn't-be-allowed" transition can be the bug, OR the model can be wrong. Manual disambiguation is heavy.
3. **The other 4 plugin ideas cover ~5 of 8 Bykea rows.** State-machine fuzzing covers 2 more — incremental value over a hard-to-build plugin.

Build *after* the cheaper plugins ship and produce data on what's still uncovered. If at that point Logic-Flaw remains a dominant FN class across the portfolio, this becomes worth the build.

## Shape (very rough — pre-design)

- Per-program state-machine declarations in `programs/<platform>/<slug>/state_machine.yaml`: states, allowed transitions, expected response signatures.
- Fuzzer walks the graph: legal-sequence baseline + perturbations (skip transition, repeat transition, reverse, partial-batch).
- Signal: `state_machine_violation_candidate` with the sequence + expected vs observed response.

## Effort

High — probably **a week or more** including the per-program model authoring. Realistic estimate after the prerequisites land.

## Prerequisites

- [[2026-05-15-authenticated-recon-primitive]] — auth needed for almost all state-machine flows.
- Operator-authored state-machine YAML per program — meaningful operator-side work.

## Hard rules

- Policy tier from `scope.md`: `rate-limited-OK` only. Out-of-order / invalid-transition probing is active recon.
- `roe.md` rate cap binds; the fuzzer's state-graph traversal must respect it (1 step per second on Bykea).
- **Probing inconsistent / partially-cancelled states is destructive by definition.** Only fire on disposable resources — operator-owned trips with synthetic riders/drivers, or program-provided test fixtures listed in `roe.md`'s `authorized_test_environments`. Never probe state-transitions on a real customer's trip / order / record.
- Cleanup invariant: every state perturbation the plugin issues must have a documented rollback path. The fuzzer maintains a rollback log per run and the operator-CLI for inspection lands in Phase C.
- PII: same redacted-screenshot rule as the rest of the runner family. Inconsistent state revealed via leaked PII triggers stop-and-report, not continued probing.

## Estimated value-add

Covers up to 3 of 8 Bykea disclosures (the three Logic-Flaws), though `/reports/2894018` is also catchable by `idor-probe`'s paired-ID mutation variant — net direct value is 2 if that plugin lands first. Possibly more cross-portfolio if Logic-Flaw stays universal. Cost-per-catch is the worst of the five candidates. **Defer.**
