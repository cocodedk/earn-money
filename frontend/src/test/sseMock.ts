/**
 * Minimal EventSource mock for JSDOM tests (6D SSE slice).
 *
 * JSDOM doesn't ship `EventSource`. This mock provides just enough of the
 * EventSource surface for the `useScanRunEvents` hook tests: construction
 * registers the instance, `open` fires on a microtask (so tests can attach
 * handlers first), `emit` dispatches `message` events while open, `fail`
 * triggers `error`, and `close` is idempotent.
 *
 * Uses only DOM `Event` / `MessageEvent` types — do NOT import the API
 * `Event` from `../types/api` here; the names collide.
 */

export class MockEventSource {
  static instances: MockEventSource[] = [];
  // When false, newly-constructed instances do NOT auto-fire `onopen`. Tests
  // that need to drive failure-without-open (reconnect/backoff) flip this off
  // for the windows where they want full control over open vs fail.
  static autoOpen = true;

  readonly url: string;
  readyState: 0 | 1 | 2 = 0;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    if (!MockEventSource.autoOpen) return;
    queueMicrotask(() => {
      if (this.readyState === 2) return;
      this.readyState = 1;
      this.onopen?.(new Event("open"));
    });
  }

  emit(eventObj: unknown): void {
    if (this.readyState !== 1) return;
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(eventObj) }),
    );
  }

  fail(): void {
    this.readyState = 2;
    this.onerror?.(new Event("error"));
  }

  close(): void {
    this.readyState = 2;
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
  }
}

export function installMockEventSource(): () => void {
  const g = globalThis as { EventSource?: unknown };
  const original = g.EventSource;
  g.EventSource = MockEventSource as unknown as typeof EventSource;
  MockEventSource.instances = [];
  MockEventSource.autoOpen = true;
  return () => {
    g.EventSource = original as typeof EventSource | undefined;
    MockEventSource.instances = [];
    MockEventSource.autoOpen = true;
  };
}
