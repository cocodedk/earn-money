# Slice F — Per-program rate limit via token bucket

1. `test_rate_limit.py` failing → a token-bucket of capacity=10, refill=10/sec allows 10 immediate requests, blocks the 11th for ~100ms.
2. **Floor-precedence test** (per decision-doc §6): when the program's `roe.max_requests_per_second=10` and the shared scanner floor is `2`, the actual cap binds at `min(10, 2) = 2 r/s`. When the program cap is `1` (tighter than the floor), the cap binds at `1 r/s`. Lower always wins.
3. Cross-worker test/design note from AUDIT: use the existing shared cache/Redis primitive when multiple worker processes can run Phase 1. Key by `(platform, slug)` and make updates atomic enough that two workers cannot both consume the last token. If no shared primitive exists, force single-worker execution for live smoke and track distributed limiter as a blocking follow-up before broad scans.
4. `rate_limit.py` — per-program token bucket, keyed by `(platform, slug)`. Tests cover clock injection, cache key isolation, non-positive caps rejected by loader, and no sleep while holding locks.
5. Wire into the fetcher (`_shared/http.py` lift, or per-stub fetcher) after `enforce_scope` passes and before any network call.
6. Commit: `feat(programs): per-program token-bucket rate limit + floor-precedence honoring roe.max_requests_per_second`.
