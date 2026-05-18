# Phase 5 — SSE hook + EventList wiring

`useScanRunEvents(scanRunId)` wraps native `EventSource`, exposes the events array + connection state, handles reconnect with backoff + `Last-Event-ID` resume, and falls back to polling `/api/scan-runs/<id>/events/` if SSE fails repeatedly. Per `12-live-events.md` and peer's SSE contract from commit `10aaf49`.

---

### Task O: `useScanRunEvents` hook

**Files:**
- Create: `frontend/src/lib/useScanRunEvents.ts`
- Create: `frontend/src/lib/useScanRunEvents.test.tsx`

The hook returns:
- `events: ScanEvent[]` — accumulated frames in arrival order
- `status: "connecting" | "open" | "polling" | "closed"` — current connection mode
- `lastEventId: string | null` — for diagnostics and Last-Event-ID resume

Behavior:
- Open `EventSource(\`/sse/scan-runs/${scanRunId}/events/\`)` on mount.
- On `onmessage`, parse JSON, append to events.
- On `onerror`, close the source. If failure count < 3, retry after 1s, 2s, 4s with `Last-Event-ID` header (passed via URL query for SSE since `EventSource` can't set headers directly — peer's server reads `?last_event_id=` as a fallback; if not, accept the missed-events gap).
- After 3 failures, switch to polling mode: `useQuery` on `/api/scan-runs/<id>/events/` with `refetchInterval: 2000`. The list-of-events response replaces accumulated events on each tick. Status flips to `polling`.
- On unmount, close the source.
- When scanRunId changes, reset state + reopen.

- [ ] **Step 1: Test** — using MSW's SSE support and `jsdom`'s `EventSource` shim. Test cases:
  1. Receives events in order from the SSE stream.
  2. Accumulates across multiple frames.
  3. Reconnects with `last_event_id` query after a single error.
  4. Falls back to polling after 3 consecutive errors.
  5. Closes the source on unmount.
  6. Resets state when scanRunId changes.

Note: `jsdom` does not include `EventSource` natively. Add `event-source-polyfill` or stub `globalThis.EventSource` in `src/test/setup.ts`. The mock implementation should expose `.send(data)` / `.error()` helpers for tests.

A minimal mock in `src/test/sseMock.ts`:

```ts
type Listener = (e: MessageEvent) => void;
type ErrorListener = (e: Event) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  withCredentials = false;
  readyState = 1;
  CONNECTING = 0;
  OPEN = 1;
  CLOSED = 2;
  onmessage: Listener | null = null;
  onerror: ErrorListener | null = null;
  onopen: ((e: Event) => void) | null = null;
  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  close() {
    this.readyState = 2;
  }
  emit(data: unknown, id?: string) {
    this.onmessage?.(new MessageEvent("message", {
      data: typeof data === "string" ? data : JSON.stringify(data),
      lastEventId: id ?? "",
    }));
  }
  error() {
    this.readyState = 2;
    this.onerror?.(new Event("error"));
  }
}

export function installSseMock() {
  MockEventSource.instances = [];
  (globalThis as any).EventSource = MockEventSource;
}

export function lastSseInstance(): MockEventSource | undefined {
  return MockEventSource.instances.at(-1);
}
```

- [ ] **Step 2: Implement `useScanRunEvents.ts`** with the behaviors described above. Use `useRef` for the `EventSource` instance, `useState` for events + status + failure count. The polling fallback uses `useQuery` conditionally enabled.

- [ ] **Step 3: Commit + /simplify**

```bash
npm run test -- src/lib/useScanRunEvents
git add frontend/src/lib/useScanRunEvents.{ts,test.tsx} frontend/src/test/sseMock.ts frontend/src/test/setup.ts
git commit -m "feat(frontend): add useScanRunEvents hook (SSE + polling fallback)"
```

---

### Task P: Wire `useScanRunEvents` to `EventList`

A thin wrapper `LiveEventsPanel` that pulls events from the hook and renders them via `EventList`. Used inside the scan-run detail page (phase 6).

**Files:**
- Create: `frontend/src/features/scan-runs/LiveEventsPanel.tsx`
- Create: `frontend/src/features/scan-runs/LiveEventsPanel.test.tsx`

```tsx
import { EventList } from "../../components/EventList";
import { useScanRunEvents } from "../../lib/useScanRunEvents";

export type LiveEventsPanelProps = { scanRunId: string };

export function LiveEventsPanel({ scanRunId }: LiveEventsPanelProps) {
  const { events, status } = useScanRunEvents(scanRunId);
  return (
    <div data-testid="live-events-panel" data-status={status}>
      <EventList events={events} />
    </div>
  );
}
```

Test asserts:
1. Streams events through to `EventList`.
2. Surfaces the connection status as `data-status`.

- [ ] **Step 1: Test + implement + commit + /simplify**
