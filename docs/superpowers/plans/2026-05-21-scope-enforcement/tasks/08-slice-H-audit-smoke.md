# Slice H — Post-impl audit + live smoke against algolia

1. Spec-review report at `docs/superpowers/spec-reviews/2026-05-21-scope-enforcement.md` confirming every must-not from CLAUDE.md is enforced by code or test.
2. Create RECON_ENABLED flag-file at repo root (operator confirms), then verify containers see it at `settings.RECON_ENABLED_PATH`.
3. Live in-scope smoke: dispatch stub 1.1 + 1.2 + 1.3 + 1.20 against `www.algolia.com` (in scope), confirm probes happen, rate limit stays within `roe.max_requests_per_second`, findings emit, and no `OUT_OF_SCOPE_REJECTED` events appear.
4. Pre-flight negative smoke: attempt the SAME stubs against `out-of-scope.example.invalid`; confirm scan-run creation/start refuses before enqueue and zero HTTP traffic occurs. This does not produce fetcher-level events because pre-flight blocks it.
5. Fetcher negative smoke: with an in-scope target and a controlled candidate list containing one out-of-scope URL, confirm `OUT_OF_SCOPE_REJECTED` emits and the HTTP client mock/proxy observes zero network I/O for that candidate.
6. Remove the smoke `RECON_ENABLED` flag after verification unless the operator explicitly keeps it for continued live testing.
7. Commit: `docs(stub-reviews): scope-enforcement post-impl audit + algolia smoke test`.
