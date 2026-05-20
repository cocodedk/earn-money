# Verification gate — Phase 2

Before any Phase 2 stub is claimed "done":

## Static gates

1. **TDD coverage**: 100% line + branch on the stub's runner + helpers.
   Measured via `pytest apps/stubs/<stub_pkg>/ --cov=apps.stubs.<stub_pkg>
   --cov-branch --cov-fail-under=100`.
2. **Cross-stub regressions**: `apps/stubs/test_runner_guard_wiring.py`
   green — the new stub is registered AND respects scope-enforcement.
3. **Spec-review report**: filed under
   `docs/superpowers/spec-reviews/2026-05-21-stub-<slug>-<name>.md`,
   covering every spec assertion (positive + negative).
4. **/simplify clean**: zero high-confidence findings after each commit
   in the stub's slice.

## Live gates

5. **Fixture smoke**: scan-on-vps.sh from h1 against the stub's
   fixture target completes status=done with the expected Finding /
   AUTH_PROBE_REFUSED / AUTH_FIXTURE_REQUIRED outcome.
6. **Negative smoke**: same scan against an OOS host refuses at
   preflight, no Celery enqueue, no HTTP fired.
7. **RoE-off smoke**: same scan with the relevant `allow_*` knob
   set to `false` in the fixture's roe.md emits
   AUTH_PROBE_REFUSED with reason="roe_disabled" and NO active
   submits.

## Phase-2-close gate (slice 24)

8. **Aggregate spec-review** at
   `docs/superpowers/spec-reviews/2026-05-21-phase-2-authentication.md`,
   mapping every CLAUDE.md hard rule + every spec assertion to its
   enforcement code path + test.
9. **No follow-up issues open** in the per-stub spec-reviews.
10. **em-frontend ACK** on the final EventType + Finding.category
    surface — confirming their UI handles every new event type
    introduced by Phase 2.
11. **Operator sign-off** before squash-merging the Phase 2 tip
    into `main`.
