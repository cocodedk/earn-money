# Phase 1 Task 7 — useScanRunEvents polling fallback

## Task 7: `useScanRunEvents` — polling fallback

**Files:**
- Modify: `frontend/src/features/scan-runs/useScanRunEvents.ts`
- Test: `frontend/src/features/scan-runs/useScanRunEvents.polling.test.tsx`

**Behaviour added:**
- On entering `polling-fallback`: stop SSE entirely; start a 2 s polling loop hitting `GET /api/scan-runs/<uuid>/events/` (em-backend-confirmed route 2026-05-20 — see `00-overview.md` §Backend lock).
- **Last-Event-ID resume:** the polling request sets the `Last-Event-ID` HTTP header to the `id` of the newest event currently in the buffer (or omits the header if the buffer is empty). Server resumes with `created_at > anchor.created_at`. Unknown anchor → fresh start (no error).
- **Result ordering:** server returns `Paginated<Event>` ordered ascending by `created_at`. Append `results` to the buffer in that order. If a returned `id` is already in the buffer, **replace in place** (same dedupe semantic as SSE path — defensive against the rare overlap with a last-second SSE message).
- **Pagination handling:** if `data.next != null` on a polling response, immediately fetch the next page (`fetch(data.next)`) and continue draining until `next === null`, then wait for the next 2 s tick. Bounded by buffer cap (default 500) — if the cap is reached during drain, evict-oldest semantics apply and we stop draining for this tick (resume on the next tick with a fresh Last-Event-ID).
- **Error handling:** if a polling response returns HTTP 5xx OR the response shape lacks `results`, log a `console.warn`, leave the buffer untouched, and retry on the next 2 s tick. Persistent 5xx (e.g. 5 consecutive failures) does NOT escalate further — we're already in the fallback path; the operator's signal is the empty/stale buffer + `polling-fallback` status pill.
- On `livePolling=false`, unmount, OR parent run reaches terminal status (`livePolling` flips false via `isRunActive` returning false on `done`/`stopped`/`failed`/`paused`): stop polling, status → `closed`.
- No automatic retry back to SSE — once we fall back, we stay in polling for this scan run's lifetime (revisit if/when SSE reliability needs measuring; Last-Event-ID makes the retry cheap if we add it later).

**Test matrix (Task 7):**
1. After 5 SSE failures → polling loop starts; status `polling-fallback`; first request hits `/api/scan-runs/<uuid>/events/`.
2. Polling tick → events appended in `created_at` ascending order.
3. `livePolling=false` while polling → status `closed`, polling stops.
4. Unmount while polling → polling stops, no leaks (verify via `MockEventSource.instances` count + no in-flight fetches).
5. `clear()` while polling → buffer empties; polling continues; **next polling request sends NO `Last-Event-ID` header** (buffer is empty).
6. Parent run reaches terminal status (operator sets `livePolling=false` as a result) → polling stops; status `closed` (integration-level reinforcement also covered by Phase 3 Task 5).
7. Polling tick returns a result containing an `id` already in the buffer → entry replaced in place (no duplicate row).
8. **Last-Event-ID:** with 3 events in buffer, next polling request sets `Last-Event-ID` header to the newest buffered event's `id`.
9. **Pagination drain:** server returns `next != null` on first page → second `fetch(data.next)` fires immediately within the same tick; events from both pages appended in order.
10. **Pagination cap:** with `maxBuffer=10`, server returns 15 events across 2 pages → buffer holds the newest 10, oldest 5 evicted; drain stops mid-second-page when cap reached.
11. **HTTP 500 response:** polling returns `500` → buffer untouched, status stays `polling-fallback`, next tick retries.
12. **Invalid response shape:** polling returns `{ "error": "x" }` (no `results` key) → buffer untouched, status stays `polling-fallback`.
13. **5 consecutive 500s:** polling stays in fallback, does NOT escalate to `closed` — operator triages via the status pill + empty buffer.

**Commit:** `feat(frontend): useScanRunEvents polling fallback`.
