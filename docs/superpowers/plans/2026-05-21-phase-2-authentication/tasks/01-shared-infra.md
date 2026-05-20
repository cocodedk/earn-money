# Slice 01 — Phase 2 shared infrastructure

> Foundation for stubs 2.1 through 2.22. No stub is registered in this slice.

## Scope

Build `backend/apps/stubs/_shared/auth/` with five primitives:

1. **`forms.py`** — `discover_forms()` + `AuthForm` dataclass.
   See [`../shared-infra/A-form-discovery.md`].
2. **`requests.py`** — `build_probe_pair()` + `ProbePair` dataclass.
   See [`../shared-infra/B-request-shape.md`].
3. **`normalize.py`** — `normalize()` + `diff()` + `NormalizedResponse`.
   See [`../shared-infra/C-normalization.md`].
4. **`identifiers.py`** — `generate_invalid_identifier(kind: "email" | "username")`.
   Per-scan random nonce; emails under `example.invalid`. ~30 LoC.
5. **`endpoints.py`** — `candidate_login_paths()`, `candidate_reset_paths()`,
   `candidate_register_paths()`. Pure data; no I/O.

Also:

6. **`apps/programs/roe.py`** — extend `RoE` dataclass with five new
   booleans, each defaulting to `False`. See
   [`../decisions/safety-floor.md`].
7. **`apps/events/types.py`** — three new `EventType` values:
   `AUTH_PROBE_REFUSED`, `AUTH_FINDING_CANDIDATE`, `AUTH_FIXTURE_REQUIRED`.

## Tests (strict TDD, 100% coverage)

* `test_forms.py` — form discovery + flow-hint heuristics.
* `test_requests.py` — shape-preservation + CSRF-refresh callback.
* `test_normalize.py` — strip patterns + diff semantics.
* `test_identifiers.py` — generated identifier shape + uniqueness.
* `test_endpoints.py` — candidate path list (regression catch).
* `test_roe.py` (extend) — new knobs default to `False`.

## NOT in this slice

* No runner is registered.
* No fixture-target scope.md/roe.md edits.
* No live probing — `_shared/auth/` is pure logic.
* No frontend contract changes — Event types are added but unused.

## Acceptance

* 100% line + branch coverage on the 5 new modules.
* `pytest apps/ --no-cov -q` still 1636+ passes.
* `apps/stubs/_shared/auth/__init__.py` exposes the public surface.
* em-frontend ping fired: "Phase 2 shared infra landed; three new
  EventTypes are reserved but unused until slice 02."

## Commit

`feat(stubs): Phase 2 shared auth infrastructure + new EventTypes`
