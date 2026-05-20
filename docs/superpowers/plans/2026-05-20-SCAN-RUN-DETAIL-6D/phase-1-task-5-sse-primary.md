# Phase 1 Task 5 — useScanRunEvents SSE primary path + ConnectionStatus

## Task 5: `useScanRunEvents` — SSE primary path + ConnectionStatus

**Files:**
- Create: `frontend/src/features/scan-runs/useScanRunEvents.ts` (~90 lines target; cap 200)
- Test: `frontend/src/features/scan-runs/useScanRunEvents.sse.test.tsx`

**Hook surface:**

```ts
export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "polling-fallback"
  | "closed";

export interface UseScanRunEventsResult {
  events: Event[];
  status: ConnectionStatus;
  reconnect: () => void;
  clear: () => void;
}

export function useScanRunEvents(
  scanRunId: string | undefined,
  options?: { livePolling?: boolean; maxBuffer?: number },
): UseScanRunEventsResult;
```

**Behaviour in this task (reconnect + polling deferred to Task 6 / 7):**
- On mount with `scanRunId` truthy AND `livePolling=true`: open `EventSource` against `/api/events/scan-runs/<uuid>/stream/` (route subject to em-backend confirmation per the open msg-#XXX). Status: `connecting` → `connected` on first `onopen`.
- Append each `onmessage` to the events buffer in arrival order (newest at tail). Cap buffer at `maxBuffer` (default 500); evict oldest when over.
- `clear()` zeros the local buffer; backend events untouched.
- `reconnect()` closes current EventSource and immediately reopens; status returns to `connecting`.
- On unmount or `livePolling=false`: close EventSource, status → `closed`.
- `scanRunId === undefined`: no EventSource opened, status stays `closed`.

**Test matrix (Task 5):**
1. Opens EventSource against the expected URL on mount.
2. Emits message → appended to `events` in order.
3. Multiple messages → all appended in order, dedupe by `id` (later msg with same id replaces earlier — defensive).
4. Buffer cap: emit > maxBuffer events → oldest evicted.
5. `clear()` empties buffer without closing connection (status stays `connected`).
6. `reconnect()` closes + reopens; status flips `connecting → connected` again.
7. `scanRunId === undefined`: no instance created.
8. `livePolling=false`: no instance created.
9. `livePolling` flips true → false: instance closed, status → `closed`.
10. Unmount: instance closed.

**Commit:** `feat(frontend): useScanRunEvents SSE primary path + ConnectionStatus`.
