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
- On mount with `scanRunId` truthy AND `livePolling=true`: open `EventSource` against `/api/events/scan-runs/<uuid>/stream/` (**assumed route — em-backend has been pinged for confirmation; if it differs, Phase 3 wiring fixes the URL constant in one place. Task 5 codes against the assumed URL and gates only Phase 3 on the answer**). Status: `connecting` → `connected` on first `onopen`.
- Append each `onmessage` to the events buffer in arrival order (newest at tail). Cap buffer at `maxBuffer` (default 500); evict oldest when over.
- **Dedupe semantics:** if a message with an `id` already in the buffer arrives, **replace the existing entry in place** (preserve original index) rather than append. Defensive against backend redelivery during SSE reconnect or polling-fallback overlap.
- `clear()` zeros the local buffer; backend events untouched. **Never** issues `DELETE`/`fetch` — purely local mutation.
- `reconnect()` closes current EventSource and immediately reopens; status returns to `connecting`.
- On unmount or `livePolling=false`: close EventSource, status → `closed`.
- `scanRunId === undefined`: no EventSource opened, status stays `closed`.
- `scanRunId` changes (A → B): close A's EventSource, open B's. Buffer is **cleared** on scan-run change (no carry-over across runs).
- `livePolling` flips false → true: open a fresh EventSource if `scanRunId` is truthy.

**Note on `Event` name shadowing:** `sseMock.ts` (Task 4) imports DOM types via `globalThis.Event` / `MessageEvent`. The hook's tests import the API `Event` type from `types/api.ts`. Tests must alias one of them on collision (`import type { Event as ApiEvent } from "../../types/api"`).

**Test matrix (Task 5):**
1. Opens EventSource against the expected URL on mount.
2. Emits message → appended to `events` in order.
3. Multiple messages → all appended in order; duplicate `id` **replaces in place** (no duplicate rows, no reorder).
4. Buffer cap: emit > maxBuffer events → oldest evicted.
5. `clear()` empties buffer without closing connection (status stays `connected`).
6. `clear()` does **not** issue any network call — `fetch`/`DELETE` never invoked (negative assertion per CLAUDE.md spec-review rules).
7. `reconnect()` closes + reopens; status flips `connecting → connected` again.
8. `scanRunId === undefined`: no instance created.
9. `livePolling=false`: no instance created.
10. `livePolling` flips true → false: instance closed, status → `closed`.
11. `livePolling` flips false → true (with `scanRunId` truthy): fresh instance opened, status `connecting → connected`.
12. `scanRunId` changes A → B: A's instance closed, B's instance opened against B's URL, buffer cleared.
13. Unmount: instance closed.

**Commit:** `feat(frontend): useScanRunEvents SSE primary path + ConnectionStatus`.
