# Architecture decisions (locked in)

Seven decisions taken before any code lands. Revisit only on operator instruction or codex consult.

* **`Program` is a runtime singleton, not a DB row.** Scope + RoE are file-backed (`programs/<platform>/<slug>/{scope.md,roe.md}`). A `ProgramRegistry` reads them at process start and on every scan-run-start. Cheap mtime cache; no migrations unless an existing model field's choices require one when adding the new event type. v1 used the same shape and it worked.
* **Wildcard scope matching uses hostname suffix logic, not glob.** `*.algolia.net` matches `dashboard.algolia.net` and `x.y.algolia.net`; it does not match bare `algolia.net`. Exact entries (`www.algolia.com`) match only that host. Host normalization is lower-case, port-agnostic, IDNA-aware, and strips one trailing dot. Out-of-scope entries always override in-scope entries.
* **Two enforcement layers (defense-in-depth):**
  1. **Pre-flight at scan-run-start** — `ScanRun.start()` or `ScanRunViewSet.create()` resolves the target to exactly one `Program`, raises `OutOfScope` if no program covers it, and raises `AmbiguousProgram` if two programs tie after exact/longest-suffix precedence.
  2. **Per-request inside fetcher** — every probe URL is re-checked against the already-resolved program scope inside `_shared/http.py` (or each stub's local fetcher) before any HTTP fires. Out-of-scope probe → no fire, log `OUT_OF_SCOPE_REJECTED` event exactly once, runner continues with next candidate.
* **`RECON_ENABLED` is a flag file at repo root, not an env var.** Operator creates/removes via `touch RECON_ENABLED` / `rm RECON_ENABLED`. Containers read it through a configurable `RECON_ENABLED_PATH` because bind-mounting a single optional file is unsafe when absent. Absent file → scan-run creation refuses and every active stub runner also short-circuits at entry. Passive recon (where we add it later) ignores the flag.
* **Three-tier policy gating at scan-run-start:**
  - `rate-limited-OK` → full Phase 1 stubs allowed.
  - `manual-only` → ScanRun creation refused; surfaces an explicit "operator only — scan manually" error.
  - `ambiguous` → ScanRun creation refused for ACTIVE stubs; reserved for future passive runners.
* **`max_requests_per_second` from `roe.md` honors per-program caps.** Implemented as a per-program token-bucket inside the fetcher (e.g. algolia: 10 r/s; bykea would be 1 r/s). Repo-wide floor is the LOWER of (program cap, shared cap). The bucket must be shared across worker processes via the existing cache/Redis layer when multiple workers can hit the same program; in-memory buckets are valid only for unit tests and single-worker local smoke.
* **`OUT_OF_SCOPE_REJECTED` event type** added to `EventType` enum. Emitted whenever the fetcher rejects a candidate URL.
