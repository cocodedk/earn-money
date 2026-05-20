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

> Task 5: see [phase-1-task-5-sse-primary.md](phase-1-task-5-sse-primary.md).

---

> Task 6: see [phase-1-task-6-reconnect.md](phase-1-task-6-reconnect.md).

---

> Task 7: see [phase-1-task-7-polling-fallback.md](phase-1-task-7-polling-fallback.md).

---

### Phase 1 exit criteria

- [ ] `npm test -C frontend -- --run` green (Phase-1 tests + all pre-existing 311 tests still pass).
- [ ] `npm test -C frontend -- --coverage --run` shows 100 % on `useScanRunEvents.ts` + `sseMock.ts`.
- [ ] `useScanRunEvents.ts` under 200 lines (split into `useScanRunEvents/sse.ts` + `useScanRunEvents/polling.ts` if approaching cap).
- [ ] `/simplify` round clean after each of the 7 commits.
- [ ] Em-backend confirmation **requested** (not blocking Phase 1; full blocker list lives in [`phase-3-wire-app-e2e.md`](phase-3-wire-app-e2e.md) §Blocking — SSE route, envelope, polling REST envelope, `Last-Event-ID` behaviour).
