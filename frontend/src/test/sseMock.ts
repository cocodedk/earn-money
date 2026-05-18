type Listener = (e: MessageEvent) => void;
type ErrorListener = (e: Event) => void;
type OpenListener = (e: Event) => void;

export class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  withCredentials = false;
  readyState = 0;
  CONNECTING = 0;
  OPEN = 1;
  CLOSED = 2;
  onmessage: Listener | null = null;
  onerror: ErrorListener | null = null;
  onopen: OpenListener | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.(new Event("open"));
    });
  }

  close() {
    this.readyState = 2;
  }

  emit(data: unknown, id?: string) {
    this.onmessage?.(
      new MessageEvent("message", {
        data: typeof data === "string" ? data : JSON.stringify(data),
        lastEventId: id ?? "",
      }),
    );
  }

  error() {
    this.readyState = 2;
    this.onerror?.(new Event("error"));
  }
}

export function installSseMock(): void {
  MockEventSource.instances = [];
  (globalThis as { EventSource: typeof MockEventSource }).EventSource =
    MockEventSource;
}

export function lastSseInstance(): MockEventSource | undefined {
  return MockEventSource.instances.at(-1);
}
