# Phase 1 — Event type + `useScanRunEvents` hook

**Goal:** Ship the `Event` type and the `useScanRunEvents` hook with SSE primary path, exponential-backoff reconnect, polling fallback, and explicit `ConnectionStatus` state machine. No UI yet.

**Reference patterns:**
- Type shape: `frontend/src/types/api.ts` (Finding/Evidence appended in 6C).
- Hook structure: `useScanRunFindingsQuery` in `frontend/src/features/scan-runs/api.ts` is the polling-only template; SSE primary path is **new** (no precedent in current codebase, slice-2 reservoir has a stale shape).
- MSW SSE pattern: see [`https://mswjs.io/docs/recipes/streaming/`](https://mswjs.io/docs/recipes/streaming/) — `ReadableStream` per request with `text/event-stream` content type.

---

### Task 1: Add `Event` + `EventLevel` types

**Files:**
- Modify: `frontend/src/types/api.ts` (~150 lines after 6C → ~165 after this)
- Test: none (type-only)

Type contract — append to `types/api.ts`:

```ts
export type EventLevel = "debug" | "info" | "warning" | "error";

export type Event = {
  id: Uuid;
  type: string;                  // backend renamed event_type → type
  scan_run: Uuid;
  target: Uuid | null;
  subject_type: string;
  subject_id: Uuid;
  level: EventLevel;
  message: string;
  data: Record<string, unknown>;
  created_at: Iso8601;
};
```

**Verify:** `npm run -C frontend typecheck` passes. **Commit:** `feat(frontend): add Event + EventLevel types for 6D`.

---

### Task 2: Event fixture factory

**Files:**
- Create: `frontend/src/features/scan-runs/__fixtures__/event.ts` (~18 lines)

Mirror the `makeFinding` / `makeEvidence` pattern; default to a `target_started` info-level event scoped to the standard fixture scan-run UUID.

**Commit:** `test(frontend): add Event fixture factory for 6D`.

---

### Task 3: Default MSW handler for `/api/events/`

**Files:**
- Modify: `frontend/src/test/handlers.ts`

Add an empty-list paginated handler for `GET /api/events/` (polling fallback baseline). Individual tests override with `server.use(...)`.

**Commit:** `test(frontend): default MSW handler for /api/events/`.

---

### Task 4: SSE test infrastructure

**Files:**
- Create: `frontend/src/test/sseMock.ts` (~60 lines)
- Verified-by: existing tests still green; new infra is unused yet

JSDOM doesn't ship `EventSource`. Build a minimal mock:

```ts
// Shape sketch — exact API surface refined during impl
export class MockEventSource {
  static instances: MockEventSource[] = [];
  readonly url: string;
  readyState: 0 | 1 | 2 = 0;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  // ...
  emit(eventObj: unknown): void;
  fail(): void;
  close(): void;
}

export function installMockEventSource(): () => void;  // returns restore fn
```

Tests opt in via `installMockEventSource()` in `beforeEach`, cleanup in `afterEach`. The mock surface stays minimal: support `onopen`/`onmessage`/`onerror`/`close()` + helpers for tests to drive open / emit / fail / close.

**Commit:** `test(frontend): MockEventSource test infrastructure for 6D`.

---

### Task 5: `useScanRunEvents` — SSE primary path + ConnectionStatus

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

---

### Task 6: `useScanRunEvents` — reconnect with exponential backoff

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

---

### Task 7: `useScanRunEvents` — polling fallback

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

**Commit:** `feat(frontend): useScanRunEvents polling fallback`.

---

### Phase 1 exit criteria

- [ ] `npm test -C frontend -- --run` green (Phase-1 tests + all pre-existing 311 tests still pass).
- [ ] `npm test -C frontend -- --coverage --run` shows 100 % on `useScanRunEvents.ts` + `sseMock.ts`.
- [ ] `useScanRunEvents.ts` under 200 lines (split into `useScanRunEvents/sse.ts` + `useScanRunEvents/polling.ts` if approaching cap).
- [ ] `/simplify` round clean after each of the 7 commits.
- [ ] Em-backend has confirmed SSE route + envelope shape (Phase 3 blocker, not Phase 1).
