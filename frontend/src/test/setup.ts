import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest";
import { server } from "./server";
import { MockEventSource } from "./sseMock";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  if (typeof Element.prototype.scrollIntoView !== "function") {
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      value: () => {},
      writable: true,
      configurable: true,
    });
  }
  (globalThis as { EventSource?: unknown }).EventSource = MockEventSource;
});
beforeEach(() => {
  MockEventSource.instances.length = 0;
  MockEventSource.autoOpen = true;
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
