# Slice 01 — Phase 2 shared infrastructure

> Foundation for stubs 2.1 through 2.22. No stub is registered in this slice.

## Scope

Build `backend/apps/stubs/_shared/auth/` with six primitives:

1. **`forms.py`** — `discover_forms()` + `AuthForm` dataclass.
   See [shared-infra A](../shared-infra/A-form-discovery.md).
2. **`requests.py`** — `build_probe_pair()` + `ProbePair` dataclass.
   See [shared-infra B](../shared-infra/B-request-shape.md).
3. **`normalize.py`** — `normalize()` + `diff()` + `NormalizedResponse`.
   See [shared-infra C](../shared-infra/C-normalization.md).
4. **`identifiers.py`** — `generate_invalid_identifier(kind: "email" | "username")`.
   Per-scan random nonce; emails under `example.invalid`. ~30 LoC.
   See [shared-infra D](../shared-infra/D-synthetic-ids.md).
5. **`endpoints.py`** — `candidate_login_paths()`, `candidate_reset_paths()`,
   `candidate_register_paths()`. Pure data; no I/O.
6. **`safety.py`** — `ProbeBudget`, refusal recording, unsafe-method checks,
   fixture-secret checks, and abort-signal classification. See
   [shared-infra F](../shared-infra/F-active-safety.md).

Also:

7. **`apps/programs/roe.py`** — extend `RoE` dataclass with five new
   booleans, each defaulting to `False`. See
   [safety-floor](../decisions/safety-floor.md) and
   [shared-infra E](../shared-infra/E-roe-extensions.md).
8. **`apps/events/types.py`** — three new `EventType` values:
   `AUTH_PROBE_REFUSED`, `AUTH_FINDING_CANDIDATE`, `AUTH_FIXTURE_REQUIRED`.

## Tests (strict TDD, 100% coverage)

* `test_forms.py` — form discovery + flow-hint heuristics.
* `test_requests.py` — shape-preservation + CSRF-refresh callback.
* `test_normalize.py` — strip patterns + diff semantics.
* `test_identifiers.py` — generated identifier shape + uniqueness.
* `test_endpoints.py` — candidate path list (regression catch).
* `test_safety.py` — budgets, unsafe-method refusal, missing fixture secret,
  and abort-signal classification.
* `test_roe.py` (extend) — new knobs default to `False`.

## NOT in this slice

* No runner is registered.
* No fixture-target scope.md/roe.md edits.
* No live probing — `_shared/auth/` is pure logic.
* No frontend UI dependency — Event types are reserved in backend but unused
  until slice 02 emits them.

## Prerequisites

* The scope-enforcement layer's per-HTTP rate-limit followup (slice H
  follow-up #1 from `docs/superpowers/spec-reviews/2026-05-21-scope-enforcement.md`)
  must land on the base branch before slice 01 begins. Without that,
  Phase 2 probes would acquire one token per runner-invocation
  instead of per HTTP, under-throttling burst-probe stubs.

## Acceptance

* 100% line + branch coverage on the 6 new modules.
* `pytest apps/ --no-cov -q` regression-clean against the base
  branch's test count (no test deletions).
* `apps/stubs/_shared/auth/__init__.py` exposes the public surface.
* `apps/events/types.py` contains all three reserved EventTypes and no stub
  emits them before slice 02.
* em-frontend ping fired: "Phase 2 shared infra landed; three new
  EventTypes are reserved but unused until slice 02."

## Commit

`feat(stubs): Phase 2 shared auth infrastructure + new EventTypes`
