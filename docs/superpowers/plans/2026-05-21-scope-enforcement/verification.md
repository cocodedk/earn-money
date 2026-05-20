# Verification (scope-enforcement complete when all hold)

* `pytest backend/apps/programs/` → 100% line + branch coverage.
* `pytest backend/` → full suite green; no regression in existing 1492 tests.
* Static audit confirms every Phase 1 HTTP call site routes through `enforce_scope` before `requests`, `httpx`, Django client, or shared `_shared/http.py` dispatch.
* `OUT_OF_SCOPE_REJECTED` event fires for every out-of-scope probe; never fires for in-scope.
* `RECON_ENABLED` absent → scan-run creation refuses and every active stub runner refuses to start if queued before the flag was removed.
* `programs/hackerone/algolia/scope.md` frontmatter change without worker restart → next scan-run start picks up the new `in_scope` list (mtime cache invalidation works).
* Live smoke against `www.algolia.com` produces real Findings + zero out-of-scope probes; a separate controlled out-of-scope candidate test proves the fetcher rejects before network I/O.
* All touched files ≤ 200 lines per [[feedback-strict-size-cap]].
