# Phase 1 Task 7 — useScanRunEvents polling fallback

## Task 7: `useScanRunEvents` — polling fallback

**Files:**
- Modify: `frontend/src/features/scan-runs/useScanRunEvents.ts`
- Test: `frontend/src/features/scan-runs/useScanRunEvents.polling.test.tsx`

**Behaviour added:**
- On entering `polling-fallback`: stop SSE entirely; start a 2 s polling loop hitting `/api/events/?scan_run=<uuid>` and append new events (dedupe by id).
- Polling result is `Paginated<Event>` — append `results` in `created_at` order, dedupe against buffer.
- On `livePolling=false` or unmount: stop polling, status → `closed`.
- No automatic retry back to SSE — once we fall back, we stay in polling for this scan run's lifetime (revisit if/when SSE reliability needs measuring).

**Test matrix (Task 7):**
1. After 5 SSE failures → polling loop starts; status `polling-fallback`.
2. Polling tick → events appended in order, no duplicates by id.
3. `livePolling=false` while polling → status `closed`, polling stops.
4. Unmount while polling → polling stops, no leaks.
5. `clear()` while polling → buffer empties, polling continues.
6. Parent run reaches terminal status (operator sets `livePolling=false` as a result) → polling stops; status `closed` (integration-level reinforcement also covered by Phase 3 Task 5).
7. Polling tick returns a result containing an `id` already in the buffer → entry replaced in place (no duplicate row).

**Commit:** `feat(frontend): useScanRunEvents polling fallback`.
