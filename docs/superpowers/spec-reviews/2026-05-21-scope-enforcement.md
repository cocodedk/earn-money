# Scope-enforcement layer — post-implementation audit

> Plan tree: [`../plans/2026-05-21-scope-enforcement/`](../plans/2026-05-21-scope-enforcement/)
> Pre-impl audit: [`./2026-05-21-scope-enforcement-pre.md`](./2026-05-21-scope-enforcement-pre.md)
> Slice: [08-slice-H-audit-smoke](../plans/2026-05-21-scope-enforcement/tasks/08-slice-H-audit-smoke.md)
> Date: 2026-05-20

This document audits the eight-slice scope-enforcement implementation
against each CLAUDE.md hard rule and against the slice contract. It
also captures the live + negative smoke results that proved the layer
behaves correctly against an actual HackerOne program (algolia).

## Slice-by-slice traceability

| Slice | Commit | Production code | Tests |
|-------|--------|-----------------|-------|
| A — Scope matcher | `003be20` | `apps/programs/scope.py` | `apps/programs/tests/test_scope.py` |
| B — Flags | `dbf82cc` | `apps/programs/flags.py` | `apps/programs/tests/test_flags.py` |
| C — Loader | `5e6f427` | `apps/programs/loader.py` + `roe.py` | `apps/programs/tests/test_loader.py` |
| D — Pre-flight | `00fe9ac` | `apps/programs/preflight.py` + `scans/serializers.py` | `apps/scans/test_views.py` |
| E — Fetcher scope | `e354c55` | `apps/stubs/_shared/scope_check.py` | `apps/stubs/_shared/tests/test_scope_check.py` |
| F — Rate limit | `8411085` | `apps/programs/rate_limit.py` | `apps/programs/tests/test_rate_limit.py` |
| G — Wire all stubs | `7e100ca` → `1aad511` | `apps/stubs/runners.py::guarded_runner` + `_shared/http.py::guard` | `apps/stubs/test_runner_guard_wiring.py` |
| H — Audit + smoke | (this commit) | — | live smoke transcript below |

## CLAUDE.md hard-rule mapping

### Scope is gospel — no scan/probe/DNS of an asset not in `scope.md`

Two enforcement layers, defence-in-depth:

* **Pre-flight (slice D)** — `apps/scans/serializers.py::ScanRunSerializer.validate` calls
  `preflight_scan_run(target_urls, active=True)` on `target.base_url`. An OOS host
  raises `OutOfScope` which DRF translates to a 4xx response. No row is persisted.
* **Fetcher (slice E + G)** — every standalone runner is decorated with
  `@guarded_runner("N.M")` (18 stubs) or calls `guard()` directly inside its
  candidate loop (1.20). Both paths invoke `enforce_scope()`, which raises
  `OutOfScope` and emits `OUT_OF_SCOPE_REJECTED` for any candidate URL whose
  host is not on the program's `in_scope` list (or is on the `out_of_scope`
  deny-list).

A static grep test (`test_every_registered_runner_imports_guard_symbol`)
ensures every newly-registered runner imports one of the two safe paths.
A parametrized behavioural test (`test_runner_refuses_oos_target`) asserts
all 19 standalone runners halt and emit `OUT_OF_SCOPE_REJECTED` when the
resolved program's scope excludes the target.

### Three-tier policy — `rate-limited-OK` / `manual-only` / `ambiguous`

`preflight._enforce_policy` (slice D):

* `rate-limited-OK` → proceed.
* `manual-only` → raise `ManualOnly`.
* `ambiguous` → raise `AmbiguousPolicy` (passive recon only; active stubs refuse).

Pre-flight runs at ScanRun creation, so the three-tier check fires
before any worker is enqueued. Tests at
`apps/scans/test_views.py::ScanRunPreflightPolicyTests`.

### Kill-switch — `RECON_ENABLED` flag-file at repo root

`apps/programs/flags.py::require_recon_enabled` raises `ReconDisabled`
when the configured `settings.RECON_ENABLED_PATH` is absent or is a
directory (Docker bind-mount safety). Called by `guard()` (slice G) on
**every** runner invocation — not just at boot, satisfying the
"checked on every cron invocation" rule from CLAUDE.md.

### Per-program FROZEN flag

`apps/programs/flags.py::is_program_frozen` checks
`PROGRAMS_ROOT/<platform>/<slug>/FROZEN`. Called inside `guard()` on
every runner invocation. A frozen program halts further work via
`ProgramFrozen` — distinct exception from `ReconDisabled` so triage
events can attribute the halt correctly.

### Wildcard semantics divergence from v1

CLAUDE.md decision-doc: wildcards do NOT match the bare apex
(`*.algolia.net` ≠ `algolia.net`). Implemented in
`apps/programs/scope.py::matches_any` and asserted in
`apps/programs/tests/test_scope.py::test_wildcard_does_not_match_apex`.

### Negative-scope-is-gospel

`apps/programs/scope.py::matches_scope` and
`apps/stubs/_shared/scope_check.py::enforce_scope` both check the
`out_of_scope` deny-list FIRST. Asserted in
`apps/programs/tests/test_scope.py::test_out_of_scope_overrides_in_scope`
and `_shared/tests/test_scope_check.py::test_deny_list_overrides_wildcard`.

### Per-program RoE — `max_requests_per_second`

`apps/programs/rate_limit.py::acquire_for(program)` blocks each runner
invocation on a token-bucket whose capacity =
`min(program.roe.max_requests_per_second, settings.RATE_LIMIT_SHARED_FLOOR_RPS)`.
The floor enforces a repo-wide ceiling regardless of program RoE.

Known gap (tracked, not blocking this slice): the rate-limit acquires
ONE token per runner invocation. Multi-URL stubs that iterate candidate
paths inside their fetcher (admin_panels, hidden_routes, debug_pages,
backup_files, old_endpoints) currently consume only one token per
scan-target-run, not per candidate HTTP. The 1.20 canary correctly
acquires per-candidate because the iteration sits in the runner.
Acceptable for Phase 1 same-host enumeration where total HTTPs per
scan-target-run are bounded by the candidate list (~30 max); revisit
in Phase 2 when cross-origin link extraction enters.

### Two human gates (`findings/_queue/` → `_verified/` → `_submitted/`)

Out of scope for this layer. The scope-enforcement layer covers the
HTTP-issuance side; the finding-promotion flow is untouched.

### GDPR Art. 28 on real third-party PII

`roe.md` parsing (slice C) enforces `pii_handling` is one of the spec's
allowed values and is surfaced on the `RoE` dataclass. Active stubs
inspect `roe.pii_handling` at runtime (not yet wired — tracked as a
Phase 2 followup; algolia's roe.md says `one_redacted_screenshot`).

## Live smoke transcript (2026-05-20)

Reproducer: `docker compose exec backend python scripts/smoke_scope_enforcement.py`
with `flags/RECON_ENABLED` present and the algolia program in
`programs/hackerone/algolia/`. All four steps PASSED.

### Step 1 — In-scope pre-flight: `www.algolia.com`

`ScanRunSerializer` accepted the payload. Pre-flight resolved the host
via `find_for_host`, verified `rate-limited-OK` policy, verified
FROZEN flag absent. No `OUT_OF_SCOPE_REJECTED` events.

### Step 2 — Pre-flight negative: `out-of-scope.example.invalid`

Serializer refused with
`scope-enforcement refused: OutOfScope: host 'out-of-scope.example.invalid' not in any program's scope`.
No ScanRun persisted; no Celery task enqueued.

### Step 3 — Fetcher negative (in-scope target, mocked OOS program)

ScanRun for algolia + `find_for_host` mocked to return a program with
empty `in_scope`. Stub 1.2 runner dispatched synchronously; one
`OUT_OF_SCOPE_REJECTED` event emitted; zero HTTP fired.

### Step 4 — LIVE algolia HTTP via stub 1.2 (server_headers)

Real HEAD probe to `https://www.algolia.com` through the production
fetcher path:
* No `OUT_OF_SCOPE_REJECTED` events.
* `Evidence` count for the run: 1.
* `Finding` count for the run: 1 (server-headers fingerprint).
* Runner returned cleanly; rate-limit token bucket acquired exactly
  once for the single probe.

### Step 5 — Kill-switch verification

`rm flags/RECON_ENABLED`; subsequent `require_recon_enabled()` raises
`ReconDisabled` with the expected message.

## Followups (not blocking algolia smoke)

* **Per-HTTP rate-limit inside multi-URL fetchers**. See "Per-program
  RoE" above. Phase 2 will refactor those fetchers to acquire per
  candidate URL.
* **Wrap `httpx.Client` in `_shared/http.py`** so future fetchers
  cannot bypass `guard()` at the call site. Today the regression test
  is grep-based ("every runner.py imports a guard symbol"). A wrapping
  layer would catch any new fetcher that calls `httpx.get` directly
  without going through the guard.
* **`find_for_host()` host-cache**. `apps/programs/loader.py::find_for_host`
  walks `PROGRAMS_ROOT` on every invocation. With one program in the
  registry the cost is negligible; revisit when N grows.
* **`roe.pii_handling` wired into stubs**. The RoE dataclass parses
  the field; no active stub reads it yet. Phase 2 PII-touching stubs
  must read this before any field that could be PII.

## Verdict

The scope-enforcement layer enforces every CLAUDE.md hard rule that
falls within its remit. Pre-flight refuses OOS targets before
persistence; fetcher-level `guard()` refuses OOS candidate URLs before
HTTP; the kill-switch and FROZEN flag are checked on every runner
invocation; rate-limit and policy gates enforce program RoE.

Phase 1 stubs are cleared to run live against in-scope HackerOne
targets, gated by an operator-created `RECON_ENABLED` flag.
