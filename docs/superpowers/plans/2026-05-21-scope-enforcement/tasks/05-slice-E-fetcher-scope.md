# Slice E — Fetcher-level scope check + `OUT_OF_SCOPE_REJECTED` event

1. `test_scope_check.py` failing → `_shared/scope_check.enforce_scope(target, candidate_url, program, *, scan_run=None, stub_id=None)` raises `OutOfScope` for cross-origin or hostless URLs; logs a `scan.out_of_scope_rejected` Event exactly once when `scan_run` is supplied.
2. Event payload includes `platform`, `program_slug`, `target_url`, `candidate_url`, `stub_id`, and rejection reason. Runner catches `OutOfScope`, skips that candidate, and continues.
3. Wire `enforce_scope` into stub 1.20's well_known_paths fetcher (canary integration) — every candidate URL is checked before HEAD/GET and before rate-limit wait/network dispatch.
4. Add `OUT_OF_SCOPE_REJECTED = "scan.out_of_scope_rejected"` to `EventType` enum + test. If Django detects a model-field choices migration, include it in this slice and in rollback.
5. Commit: `feat(stubs): fetcher-level scope enforcement + OUT_OF_SCOPE_REJECTED event`.
