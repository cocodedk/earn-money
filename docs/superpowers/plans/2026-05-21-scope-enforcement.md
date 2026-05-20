# Scope-enforcement layer for v2 backend

> Branch root: `feat/em-backend-scope-enforcement-plan` (stacked on `feat/em-backend-well-known-paths`)
> Goal owner: operator-set 2026-05-21 — "we must run phase 1 against a hackerone target"
> Implements: the safety scaffolding that lets v2's Phase 1 stubs fire against real bug-bounty programs without violating CLAUDE.md's hard rules ("scope is gospel", "three-tier policy", "two human gates", "kill-switch", "per-program RoE").

## Summary

v2 backend currently has **zero** references to `programs/`, `scope.md`, `roe.md`, or `RECON_ENABLED`. Dispatching a Phase 1 stub against `www.algolia.com` today would probe the host unconditionally — no scope check, no out-of-scope rejection, no master kill-switch. Before any real HackerOne / Bugcrowd / Intigriti scan can safely fire, v2 needs the scope-enforcement layer that v1 (parked at `archive/v1/src/earn_money/{scope,flags,config}.py`) shipped.

This stack rebuilds that layer cleanly for v2's Django + Celery + per-stub-runner architecture. Programs/credentials/algolia-scope are already in place; the gap is purely runtime enforcement.

## Architecture decisions (locked in)

* **`Program` is a runtime singleton, not a DB row.** Scope + RoE are file-backed (`programs/<platform>/<slug>/{scope.md,roe.md}`). A `ProgramRegistry` reads them at process start and on every scan-run-start. Cheap mtime cache; no migrations. v1 used the same shape and it worked.
* **Wildcard scope matching uses hostname suffix logic, not glob.** `*.algolia.net` matches `dashboard.algolia.net` and `x.y.algolia.net`. Exact entries (`www.algolia.com`) match only that host. Port-agnostic by default. Implementation lifted from `archive/v1/src/earn_money/scope.py` with adaptations for the new persistence model.
* **Two enforcement layers (defense-in-depth):**
  1. **Pre-flight at scan-run-start** — `ScanRun.start()` resolves the target to a `Program`, raises `OutOfScope` if no program covers it.
  2. **Per-request inside fetcher** — every probe URL is re-checked against the program scope inside `_shared/http.py` (or each stub's local fetcher) before any HTTP fires. Out-of-scope probe → no fire, log `OUT_OF_SCOPE_REJECTED` event, runner continues with next candidate.
* **`RECON_ENABLED` is a flag file at repo root, not an env var.** Operator creates/removes via `touch RECON_ENABLED` / `rm RECON_ENABLED`. Absent file → every active stub runner short-circuits at entry. Passive recon (where we add it later) ignores the flag.
* **Three-tier policy gating at scan-run-start:**
  - `rate-limited-OK` → full Phase 1 stubs allowed.
  - `manual-only` → ScanRun creation refused; surfaces an explicit "operator only — scan manually" error.
  - `ambiguous` → ScanRun creation refused for ACTIVE stubs; reserved for future passive runners.
* **`max_requests_per_second` from `roe.md` honors per-program caps.** Implemented as a per-program token-bucket inside the fetcher (e.g. algolia: 10 r/s; bykea would be 1 r/s). Repo-wide floor is the LOWER of (program cap, shared cap).
* **`OUT_OF_SCOPE_REJECTED` event type** added to `EventType` enum. Emitted whenever the fetcher rejects a candidate URL.

## File structure to create

* `backend/apps/programs/` — new Django app.
  - `apps.py` — `ProgramsConfig`.
  - `loader.py` — `Program` dataclass + `ProgramRegistry` reading `programs/<platform>/<slug>/{scope.md,roe.md}`. Mtime cache.
  - `scope.py` — `Scope` dataclass + `matches_scope(host, in_scope, out_of_scope) -> bool` (wildcard suffix logic).
  - `flags.py` — `require_recon_enabled()` / `is_program_frozen()` / `ReconDisabled` / `ProgramFrozen`.
  - `roe.py` — `RoE` dataclass with `max_requests_per_second`, `dos_authorized`, etc.
  - `rate_limit.py` — per-program token-bucket honoring `roe.max_requests_per_second`.
  - `tests/` — split per cap.
* `backend/apps/scans/models.py` — extend `ScanRun.start()` (or `create_scan_run` view-helper) with the pre-flight scope check.
* `backend/apps/stubs/_shared/scope_check.py` — NEW: `enforce_scope(target, candidate_url, program)` for fetcher-level enforcement. Each stub's fetcher calls this before issuing any request.
* `backend/apps/events/types.py` — add `OUT_OF_SCOPE_REJECTED = "scan.out_of_scope_rejected"`.
* `backend/config/settings.py` — `PROGRAMS_ROOT = Path("/programs")` (mount at the repo's `programs/` dir).
* `docker-compose.yml` — mount `./programs:/programs:ro` on `backend` + `worker`. Mount `./RECON_ENABLED:/recon_enabled:ro` (or symlink the parent so its existence reflects to the container).

## TDD slices

Stack: `feat/em-backend-scope-enforcement` off `feat/em-backend-well-known-paths` tip per [[project-stacked-branch-convention]].

### Slice 0 — AUDIT (pre-implementation)

1. Read `archive/v1/src/earn_money/{scope.py,flags.py,config.py}` end-to-end. Distill the wire format + matcher semantics + flag-file semantics.
2. Read CLAUDE.md "Hard rules" section + "Three-tier program policy" + "Per-program Rules of Engagement" + "Kill-switch". Pin the runtime contract.
3. Write audit at `docs/superpowers/spec-reviews/2026-05-21-scope-enforcement-pre.md` listing: wire formats, must-not assertions, runtime contracts, integration points with existing v2 backend.
4. Commit: `docs(stub-reviews): scope-enforcement pre-implementation audit`.

### Slice A — `apps/programs/` app skeleton + `Scope` dataclass + wildcard matcher

1. `test_scope.py` failing → `matches_scope("dashboard.algolia.net", in_scope=["*.algolia.net"], out_of_scope=[]) is True`. Coverage matrix: exact / wildcard / out-of-scope override / port-agnostic.
2. Create `apps/programs/` Django app (apps.py, registered in INSTALLED_APPS).
3. `scope.py` — `Scope` dataclass + `matches_scope()` per archived v1 implementation.
4. Commit: `feat(programs): Scope dataclass + wildcard hostname matcher`.

### Slice B — `flags.py` + RECON_ENABLED + per-program freeze

1. `test_flags.py` failing → `require_recon_enabled(paths)` raises `ReconDisabled` when the flag is absent; passes when present. `is_program_frozen(platform, slug)` returns True when `programs/<platform>/<slug>/FROZEN` exists.
2. `flags.py` per archived v1.
3. Commit: `feat(programs): RECON_ENABLED kill-switch + per-program freeze`.

### Slice C — `loader.py` + `Program` dataclass + `ProgramRegistry`

1. `test_loader.py` failing → `ProgramRegistry.get("hackerone", "algolia")` returns a `Program` with `scope.in_scope == ["www.algolia.com", "*.algolia.net", ...]` and `roe.max_requests_per_second == 10`. Cache invalidates on mtime change.
2. `loader.py` parses YAML frontmatter from `scope.md` + `roe.md`.
3. `roe.py` — `RoE` dataclass.
4. Commit: `feat(programs): Program loader + RoE dataclass + mtime cache`.

### Slice D — Scan-run pre-flight scope check

1. `test_scan_run_preflight.py` failing → creating a ScanRun for a target whose host is in-scope on a known program succeeds; out-of-scope refuses with `OutOfScope`; `manual-only` policy refuses with `ManualOnly`; missing RECON_ENABLED refuses with `ReconDisabled`.
2. Hook the check into `ScanRunViewSet.create()` (or `ScanRun.start()` action).
3. Commit: `feat(scans): pre-flight scope + RECON_ENABLED check on ScanRun creation`.

### Slice E — Fetcher-level scope check + `OUT_OF_SCOPE_REJECTED` event

1. `test_scope_check.py` failing → `_shared/scope_check.enforce_scope(target, candidate_url, program)` raises `OutOfScope` for cross-origin URLs; logs a `scan.out_of_scope_rejected` Event when called from inside a runner.
2. Wire `enforce_scope` into stub 1.20's well_known_paths fetcher (canary integration) — every candidate URL is checked before HEAD/GET.
3. Add `OUT_OF_SCOPE_REJECTED = "scan.out_of_scope_rejected"` to `EventType` enum + test.
4. Commit: `feat(stubs): fetcher-level scope enforcement + OUT_OF_SCOPE_REJECTED event`.

### Slice F — Per-program rate limit via token bucket

1. `test_rate_limit.py` failing → a token-bucket of capacity=10, refill=10/sec allows 10 immediate requests, blocks the 11th for ~100ms.
2. `rate_limit.py` — per-program token bucket, keyed by `(platform, slug)`.
3. Wire into the fetcher (`_shared/http.py` lift, or per-stub fetcher).
4. Commit: `feat(programs): per-program token-bucket rate limit honoring roe.max_requests_per_second`.

### Slice G — Wire remaining stubs through `enforce_scope`

1. `test_runner_scope.py` per stub (1.1 / 1.2 / 1.3 / 1.10 / 1.16 / 1.17 / 1.19) → asserts an out-of-scope candidate URL emits `OUT_OF_SCOPE_REJECTED` instead of issuing a real HTTP.
2. Migration: each fetcher's GET/HEAD call site adds the scope check.
3. Commit: `feat(stubs): wire all Phase 1 stubs through scope enforcement`.

### Slice H — Post-impl audit + live smoke against algolia

1. Spec-review report at `docs/superpowers/spec-reviews/2026-05-21-scope-enforcement.md` confirming every must-not from CLAUDE.md is enforced by code or test.
2. Create RECON_ENABLED flag-file at repo root (operator confirms).
3. Live smoke: dispatch stub 1.1 + 1.2 + 1.3 + 1.20 against `www.algolia.com` (in scope), confirm probes happen + findings emit. Dispatch the SAME stubs against `out-of-scope.example.invalid`, confirm `OUT_OF_SCOPE_REJECTED` events emit + zero HTTP traffic.
4. Commit: `docs(stub-reviews): scope-enforcement post-impl audit + algolia smoke test`.

## Persistence wiring

* `Scope` / `RoE` / `Program` are RUNTIME OBJECTS — never persisted to DB.
* `OUT_OF_SCOPE_REJECTED` events go through the existing `Event.log()` pathway; visible in SSE stream + REST events endpoint immediately via 6D's panel.
* `ScanRun.program_slug` could optionally be added as a CharField for triage filtering — but only if the Program model is referenced in the API. MVP: derive from target.base_url at runtime.

## Verification (scope-enforcement complete when all hold)

* `pytest backend/apps/programs/` → 100% line + branch coverage.
* `pytest backend/` → full suite green; no regression in existing 1492 tests.
* All Phase 1 stubs' fetchers route through `enforce_scope`.
* `OUT_OF_SCOPE_REJECTED` event fires for every out-of-scope probe; never fires for in-scope.
* `RECON_ENABLED` absent → every active stub runner refuses to start.
* `programs/hackerone/algolia/scope.md` change + worker restart → next scan picks up the new in_scope list (mtime cache invalidation works).
* Live smoke against `www.algolia.com` produces real Findings + zero out-of-scope probes.
* All touched files ≤ 200 lines per [[feedback-strict-size-cap]].

## Merge gate (per [[feedback-merge-heuristic]])

Stack depth ≥ 8 slices (AUDIT + A-H). Coverage 100%. Spec-review closed. No in-flight FU. → squash-merge tip into main + ping em-frontend per [[project-merge-coordination]] rule (3). No frontend impact expected (additive event type only; existing event consumers unaffected).

## Rollback

* **Disable scope enforcement** → `rm RECON_ENABLED` at repo root. Every active stub refuses to start. No DB rollback needed.
* **Revert per-slice** → `git revert <sha>`; tests catch regressions.
* **Whole-stack revert** → squash revert; programs/ directory + algolia files stay (data, not code).

## Out of scope (tracked, deferred)

* Passive-recon runners (subfinder / amass / chaos integration) — separate Phase 2 work.
* Web UI for managing programs/scope/RoE — admin via files for MVP.
* `bin/scope-sync` (H1 API → scope.md refresh) — for now, copy scope.md from v1 install on h1.cocode.dk; v2 scope-sync is its own future slice.
* Out-of-scope finding suppression in the Findings list view — `OUT_OF_SCOPE_REJECTED` events already mark them; UI filtering is a 6F slice on the frontend.
* Per-target RECON_ENABLED override (some programs paused while others run) — current MVP uses repo-wide flag. Per-program FROZEN file handles the "pause one program" case.
* `clawpwn` shared-finding bridge (`em:` / `clw:` tag namespacing per [[project-clawpwn-peer]]) — orthogonal to scope-enforcement.
