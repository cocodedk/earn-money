# Phase 1 Task 6 — useScanRunEvents reconnect with exponential backoff

## Task 6: `useScanRunEvents` — reconnect with exponential backoff

**Files:**
- Modify: `frontend/src/features/scan-runs/useScanRunEvents.ts`
- Test: `frontend/src/features/scan-runs/useScanRunEvents.reconnect.test.tsx`

**Behaviour added:**
- On `onerror`: close current EventSource, status → `reconnecting`, schedule a retry with backoff `1000 * 2^attempt` ms capped at `30_000` ms.
- After `MAX_SSE_ATTEMPTS = 5` consecutive failed reconnects (no `onopen` between them): give up — status → `polling-fallback` (polling path lands in Task 7).
- `onopen` after a reconnect → reset attempt counter to 0, status → `connected`.
- `reconnect()` called manually → reset attempt counter, immediate reopen.

**Test matrix (Task 6):**
1. SSE fails before first open → status `reconnecting`, retry scheduled at 1 s.
2. Backoff sequence: failures at attempts 1..5 happen at 1, 2, 4, 8, 16 s (next attempt would be capped at 30).
3. Successful reopen after retry → status `connected`, counter resets.
4. 5 consecutive failures with no successful open between → status → `polling-fallback`.
5. Manual `reconnect()` during backoff → cancels pending retry, opens immediately, counter resets.
6. Unmount during backoff → pending retry cancelled, no instance created.

**Commit:** `feat(frontend): useScanRunEvents exponential-backoff reconnect`.
