# Scope-enforcement layer — pre-implementation audit

> Plan tree: [`../plans/2026-05-21-scope-enforcement/`](../plans/2026-05-21-scope-enforcement/)
> Audit date: 2026-05-21
> Slice: [00-AUDIT](../plans/2026-05-21-scope-enforcement/tasks/00-slice-AUDIT.md)

## v1 reference: distilled wire format + semantics

### `archive/v1/src/earn_money/scope.py` (126 lines)

* `Scope` dataclass — frozen, 8 fields: `platform`, `slug`, `policy` (Literal `rate-limited-OK | manual-only | ambiguous`), `in_scope: list[str]`, `out_of_scope: list[str]`, `notes: str` (markdown body), `scope_hash: str`, `last_synced: str`.
* `read_scope(path)` parses YAML frontmatter via `python-frontmatter`; raises `InvalidScope` on (a) YAML parse error, (b) unknown policy, (c) missing required key. **Inherit this exception shape verbatim — only one exception type for callers to catch.**
* `_matches_any(fqdn, patterns)` does the wildcard work: lowercase the FQDN; an entry equal to the FQDN matches; `*.suffix` matches `fqdn.endswith("." + suffix)` AND `fqdn == suffix`. **Note v1 also matches the bare apex** (`*.algolia.net` matches `algolia.net`). Our v2 decision-doc says "wildcard does not match bare apex" — this is a deliberate divergence to tighten wildcards. Recorded.
* `is_in_scope(fqdn, in_scope, out_of_scope)` — out-of-scope override applies BEFORE in-scope check ("negative scope is gospel"). Same semantics for v2.
* `explicit_literals(in_scope)` — pre-computed frozenset of non-wildcard entries. Useful for sampling targets; carry to v2 verbatim.
* `compute_hash(s)` — SHA-256 of sorted `in_scope + "--" + out_of_scope`. Used by `bin/scope-sync` for change detection; v2 reuses for cache-bust signaling.

### `archive/v1/src/earn_money/flags.py` (67 lines)

* `ReconDisabled` / `ProgramFrozen` exceptions.
* `require_recon_enabled(paths)` — raises `ReconDisabled` if `paths.recon_enabled_flag` doesn't exist. **v2 adaptation:** paths come from `settings.RECON_ENABLED_PATH` (env-configurable per decision-doc; container default `/flags/RECON_ENABLED`). Add a guard so a directory-at-path also raises `ReconDisabled` (Docker single-file bind-mount safety).
* `is_program_frozen(paths, platform, slug)` — returns True if `programs/<platform>/<slug>/FROZEN` exists.
* `freeze_program` / `unfreeze_program` / `freeze_reason` / `freeze_reason_text` — operator triage helpers; carry to v2 verbatim.
* `require_program_not_frozen(paths, platform, slug)` — raises `ProgramFrozen` with the reason text. v2 keeps this exact API.

### `archive/v1/src/earn_money/config.py` (39 lines)

* `Paths` frozen dataclass: `root`, `programs`, `recon_outputs`, `recon_enabled_flag`. Factory `from_root(root)`.
* Helper methods: `program_dir(platform, slug)`, `scope_file`, `roe_file`, `freeze_flag`, `program_db`.
* **v2 adaptation:** replace `Paths.from_root()` with Django `settings.PROGRAMS_ROOT` + `settings.RECON_ENABLED_PATH` lookups. Keep the helper methods on a `ProgramPaths` class (or module-level functions) so callers don't construct paths by hand.

## CLAUDE.md hard rules pinned

From v1's CLAUDE.md (reviewed; identical to v2's runtime contract per the plan):

* **Scope is gospel** — no scan, probe, or DNS of an asset not in `scope.md` for its program. Wildcards resolve at scan time; OOS blocklist checked first.
* **Three-tier policy** — `rate-limited-OK` / `manual-only` / `ambiguous`. Runners refuse to start when policy forbids.
* **Kill-switch** — `RECON_ENABLED` flag at repo root. Every runner checks **on every cron invocation, not just at boot**. Per-program FROZEN flags gate per-program recon independently.
* **Per-program RoE** — `roe.md` declares technique-level authority. Loaded at runtime by active runners. Floor unless overridden: no DoS, no destructive, no social engineering, PII synthetic_data_only.
* **GDPR Art. 28 + Scope** — invariants that survive any program ToS.

## v2 integration points inventory

### Scan-run creation / start path

* `apps.scans.views.ScanRunViewSet.create()` (POST `/api/scan-runs/`) — creates the row, dispatches `run_scan.delay(run.id)`.
* `apps.scans.views.ScanRunViewSet.start()` action (POST `/api/scan-runs/<id>/start/`) — re-dispatches.
* Both paths converge on `transaction.on_commit(lambda: run_scan.delay(...))`. **Hook the pre-flight check here in slice D — before `on_commit`, before any task enqueue.**

### Runner entry points

* All registered runners go through `apps.scans.tasks._process_target_run` → `runner(scan_run, target_run)`. **Add `require_recon_enabled()` + `require_program_not_frozen()` at the dispatcher level (one call site) so every runner inherits the kill-switch + freeze check without per-stub wiring.**

### Phase 1 HTTP call sites (every standalone fetcher)

| Stub | Fetcher path | HTTP client | Call sites |
|------|--------------|-------------|------------|
| 1.1 framework_detection | `framework_detection/fetcher.py` | httpx.Client | 1 GET |
| 1.2 server_headers | inline (`server_headers/runner.py`) | httpx.Client | 1 GET |
| 1.3 frontend_framework | `frontend_framework/fetcher.py` | httpx.Client | 1 GET |
| 1.4 backend_hints | `backend_hints/fetcher.py` | httpx.Client | 1 GET |
| 1.5 package_leaks | `package_leaks/fetcher.py` | httpx.Client | 1 GET |
| 1.6 hidden_routes | `hidden_routes/fetcher.py` | httpx.Client | multi-path probes |
| 1.7 backup_files | `backup_files/fetcher.py` | httpx.Client | multi-path probes |
| 1.8 admin_panels | `admin_panels/fetcher.py` | httpx.Client | multi-path probes |
| 1.9 old_endpoints | `old_endpoints/fetcher.py` | httpx.Client | multi-path probes |
| 1.10 debug_pages | inline (`debug_pages/runner.py`) | httpx.Client | multi-path probes |
| 1.11 robots_txt | `robots_txt/fetcher.py` | httpx.Client | 1 GET |
| 1.12 sitemap_xml | `sitemap_xml/fetcher.py` | httpx.Client | 1 GET (+ recursion) |
| 1.13 security_txt | inline (`security_txt/runner.py`) | httpx.Client | 2 GETs |
| 1.14 source_maps | `source_maps/fetcher.py` | httpx.Client | multi-bundle |
| 1.15 public_javascript_bundles | `public_javascript_bundles/fetcher.py` | httpx.Client | multi-bundle |
| 1.16 stack_traces | `stack_traces/fetcher.py` | httpx.Client | 2 GETs |
| 1.17 verbose_api_errors | `verbose_api_errors/fetcher.py` | httpx.Client | 2 GETs |
| 1.19 sql_orm_errors | `sql_orm_errors/fetcher.py` | httpx.Client | 2 GETs |
| 1.20 well_known_paths | `well_known_paths/fetcher.py` | httpx.Client | HEAD + Range-GET × ~236 candidates |

18 standalone runners (matches the plan slice G inventory). 1.18 absorbed by 1.10; 1.21–1.25 absorbed by 1.20. **All fetchers use `httpx.Client` directly** — there's no shared `_shared/http.py` yet (its lift is a tracked Phase-1-close follow-up). Slice G must wire each fetcher individually; the `_shared/http.py` lift is orthogonal but recommended as a follow-up so future fetchers inherit `enforce_scope` automatically.

### Cache / Redis primitive

* `redis:7-alpine` already in compose; reachable at `redis://redis:6379/0` (env: `REDIS_URL`). Celery broker uses DB 0; can use DB 1 for rate-limit tokens.
* Django cache backend not currently configured for Redis — uses local-mem. **Add `django-redis` to slice F if cross-worker rate-limit is needed; for current single-worker dev, in-memory bucket is acceptable but record the distributed-limiter follow-up.**

### Event type behavior

* `apps.events.models.Event` has free-form `type` field; `EventType.choices` constrains valid values via `TextChoices`. Adding `OUT_OF_SCOPE_REJECTED` → Django generates a migration on `type` field's `choices` change. Slice E commits include the migration; rollback step covers it.

### Docker-compose mounts

* Current: `./backend:/app` (Django source), `./docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK:/cookbook:ro` (cookbook tree).
* Add: `./programs:/programs:ro` (scope + RoE files).
* Add: `./flags:/flags:ro` (directory containing optional RECON_ENABLED file — never bind-mount a single-file path that may not exist; Docker will create a directory).

## Wire format confirmed (algolia)

`programs/hackerone/algolia/scope.md` has YAML frontmatter with all fields the v1 `read_scope()` expects:
```yaml
platform: hackerone
slug: algolia
policy: rate-limited-OK
in_scope: ["www.algolia.com", "*.algolia.net", "*.algolianet.com", "dashboard.algolia.com"]
out_of_scope: []
scope_hash: 61d7e4690a381a8509e56e1739696037e7db2f018c13627043c2a2bfa39fe890
last_synced: '2026-05-13T23:19:47Z'
```

`programs/hackerone/algolia/roe.md` has:
```yaml
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: one_redacted_screenshot
max_requests_per_second: 10
authorized_test_environments: []
authorized_test_accounts: []
special_notes: |
  Algolia's H1 program — onboarded 2026-05-14...
```

Both files parse cleanly with `python-frontmatter`. Loader signatures pin to these exact fields in slice C.

## Must-not assertions (consolidated regression grid)

Code or test must enforce each:

1. **No HTTP issued without `require_recon_enabled` passing** — fetcher-level + dispatcher-level.
2. **No HTTP issued to a host not in scope** — `enforce_scope` raises `OutOfScope`; runner catches, logs `OUT_OF_SCOPE_REJECTED`, skips candidate.
3. **No ScanRun creation against an out-of-scope target** — pre-flight refuses with 4xx.
4. **No ScanRun creation when `policy=manual-only`** — pre-flight refuses with `ManualOnly`.
5. **No ScanRun creation when `policy=ambiguous`** — pre-flight refuses with `AmbiguousPolicy` for ACTIVE stubs.
6. **No ScanRun creation when `programs/<platform>/<slug>/FROZEN` exists** — pre-flight refuses with `ProgramFrozen`.
7. **No ScanRun creation when RECON_ENABLED flag absent** — pre-flight refuses with `ReconDisabled`.
8. **No rate-limit bypass** — token bucket enforced before every network call; lower of (program cap, shared floor) wins.
9. **No cross-worker token-bucket race** — distributed limiter via Redis cache OR single-worker enforcement.
10. **No out-of-scope finding silently persisted** — fetcher level rejects BEFORE classifier/persistence reaches.
11. **No duplicate `OUT_OF_SCOPE_REJECTED` events for the same candidate** — idempotent emit per `(scan_run, target, candidate_url)`.
12. **Wildcards do not match bare apex** — `*.algolia.net` ≠ `algolia.net` per the v2 decision-doc divergence.

## Runtime contracts pinned

* `ProgramRegistry.find_for_host(host: str) -> Program` — exact-literal > longest-wildcard; tie → `AmbiguousProgram`; no match → `OutOfScope`.
* `Program` runtime context attached to `ScanRun` after pre-flight; runners/fetchers receive it; **fetchers do not re-resolve from URL**.
* `enforce_scope(target, candidate_url, program, *, scan_run=None, stub_id=None) -> None` raises `OutOfScope`; emits `OUT_OF_SCOPE_REJECTED` event when `scan_run` supplied.
* `OUT_OF_SCOPE_REJECTED` event payload: `{platform, program_slug, target_url, candidate_url, stub_id, reason}`.
* Per-program token-bucket: keyed by `(platform, slug)`; capacity = `roe.max_requests_per_second`; refill = same; shared via Redis (or in-memory + single-worker assertion).

## Audit verdict

**Spec internally consistent.** v1's primitives transfer cleanly; v2 adaptations are well-scoped (Django settings, container paths, runtime-context attachment, cross-worker rate limit). 18-runner inventory matches slice G's expected coverage. Algolia files are already in place and parse-ready. No new shared types needed; no blocking unknowns. Proceeding to slice A (Scope dataclass + matcher).
