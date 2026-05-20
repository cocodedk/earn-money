import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { installMockEventSource } from "../../test/sseMock";
import { makeEvent } from "./__fixtures__/event";
import { mountAndEnterFallback } from "./__fixtures__/sseTestHelpers";

let uninstall: () => void;
beforeEach(() => {
  uninstall = installMockEventSource();
  localStorage.removeItem("disable_live_events");
});
afterEach(() => {
  vi.useRealTimers();
  uninstall();
  localStorage.removeItem("disable_live_events");
});

describe("useScanRunEvents — polling fallback dedupe & resume", () => {
  it("duplicate id in polling result → entry replaced in place", async () => {
    let phase: "first" | "second" = "first";
    server.use(
      msw.get("/api/scan-runs/:id/events/", () => {
        if (phase === "first") {
          return HttpResponse.json({
            count: 1,
            next: null,
            previous: null,
            results: [makeEvent({ id: "e1", message: "v1" })],
          });
        }
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeEvent({ id: "e1", message: "v2" })],
        });
      }),
    );
    const { result } = await mountAndEnterFallback();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events.length).toBe(1);
    phase = "second";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events[0].message).toBe("v2");
    expect(result.current.events).toHaveLength(1);
  });

  it("Last-Event-ID header is set to the newest buffered event's id", async () => {
    const seen: (string | null)[] = [];
    let phase: "first" | "second" = "first";
    server.use(
      msw.get("/api/scan-runs/:id/events/", ({ request }) => {
        seen.push(request.headers.get("Last-Event-ID"));
        if (phase === "first") {
          return HttpResponse.json({
            count: 3,
            next: null,
            previous: null,
            results: [
              makeEvent({ id: "e1", created_at: "2026-05-20T08:00:00Z" }),
              makeEvent({ id: "e2", created_at: "2026-05-20T08:00:01Z" }),
              makeEvent({ id: "e3", created_at: "2026-05-20T08:00:02Z" }),
            ],
          });
        }
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { result } = await mountAndEnterFallback();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events.length).toBe(3);
    phase = "second";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(seen[0]).toBeNull();
    expect(seen[seen.length - 1]).toBe("e3");
  });
});
