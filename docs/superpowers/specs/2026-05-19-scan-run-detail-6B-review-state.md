# 6B design review state

Portable review state for [`2026-05-19-scan-run-detail-6B-design.md`](2026-05-19-scan-run-detail-6B-design.md). Pass this file to codex on resumed verification — codex does not need to re-read the full spec, just the diff + this state.

## Status

**Ready for resumed codex cleanup verification.** Lint clean against [`2026-05-19-scan-run-detail-6B-lint.yaml`](2026-05-19-scan-run-detail-6B-lint.yaml). Codex usage limit blocked the round-7 cleanup-verify (resets 2026-05-20 02:38 local). Prepared verification prompt: [`2026-05-19-scan-run-detail-6B-cleanup-verify-prompt.md`](2026-05-19-scan-run-detail-6B-cleanup-verify-prompt.md). Verified backend anchors (don't re-grep): [`2026-05-19-scan-run-detail-6B-backend-anchors.md`](2026-05-19-scan-run-detail-6B-backend-anchors.md).

## Loop summary

Codex mutual-acceptance loop (gpt-5.5 xhigh, `read-only` sandbox). After rounds 1-6 codex returned 21 issues across the design contract, test coverage, backend SHA pinning, and terminology consistency; all addressed in the current revision of the spec.

## Stable since round 4 — do not re-litigate

§Type contract, §Column layout (incl. per-row test-id), §Files (all rows), §Decisions items 1-4, §Acceptance criteria, §Out of scope, §Backend pagination policy (`PAGE_SIZE = 50` at `backend/config/settings.py:138`), §Prerequisites SHA pin (`e93c6f4`), §Tests row-timestamp split (stopped-from-queued vs stopped-from-running), §Decisions item 4 (DetailPageGuard narrowing on `!query.data` for both 404 and generic-error branches).

## Changed in response to codex round 5 (BLOCKER)

- §Hook contract terminal-flush rule: replaced the old `invalidateQueries` + `cancelRefetch: true` form with a two-step `cancelQueries` + `refetchQueries` pattern. `invalidateQueries` only cancels in-flight *refetches* (cached data exists); it does NOT cancel an in-flight *initial* fetch. The no-cached-data edge would let a stale pre-terminal response land after polling is off.
- §Tests `api.target-runs.test.tsx`: split the in-flight flush test into two branches — "cached data exists" (existing) and "no cached data (initial fetch in flight)" (new, round-5 edge case).
- §Tests `ScanRunDetail.target-runs.test.tsx`: added the matching no-cached-data branch at the integration level.

## Changed in response to codex round 6 (contradiction cleanup)

- §Render integration worker-driven flow step 4: dropped the "invalidate-and-refetch" wording (leftover from pre-round-5 contract); now reads "two-step `cancelQueries` + `refetchQueries` pair" matching §Hook contract.
- §Tests `ScanRunDetail.target-runs.test.tsx` — `running → done` and `running → stopping → stopped` bullets: dropped "exactly one refetch fires" / "no-op'd by `cancelRefetch: false`" wording (also leftover); both now assert cache content (fresh terminal rows committed) consistent with the §Hook contract terminal-flush rule.

## Pending — for codex resumed cleanup verify

Validate the round-6 cleanup landed; spot any remaining `invalidate` / `cancelRefetch` leftovers. Stable sections unchanged from prior rounds. Lint passes locally; codex's job is to catch judgment-level contradictions the lint can't.
