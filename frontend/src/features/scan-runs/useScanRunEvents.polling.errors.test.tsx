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

describe("useScanRunEvents — polling fallback error handling", () => {
  it("HTTP 500 → buffer untouched, status stays polling-fallback, retries next tick", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    let phase: "ok" | "err" | "ok2" = "ok";
    server.use(
      msw.get("/api/scan-runs/:id/events/", () => {
        if (phase === "err") return new HttpResponse(null, { status: 500 });
        const id = phase === "ok" ? "e1" : "e2";
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeEvent({ id })],
        });
      }),
    );
    const { result } = await mountAndEnterFallback();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events.length).toBe(1);
    phase = "err";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events).toHaveLength(1);
    expect(result.current.status).toBe("polling-fallback");
    phase = "ok2";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events.length).toBe(2);
    warn.mockRestore();
  });

  it("invalid response shape (no results) → buffer untouched, status unchanged", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    let phase: "ok" | "bad" = "ok";
    server.use(
      msw.get("/api/scan-runs/:id/events/", () => {
        if (phase === "bad") return HttpResponse.json({ error: "x" });
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeEvent({ id: "e1" })],
        });
      }),
    );
    const { result } = await mountAndEnterFallback();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events.length).toBe(1);
    phase = "bad";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events).toHaveLength(1);
    expect(result.current.status).toBe("polling-fallback");
    warn.mockRestore();
  });

  it("5 consecutive 500s → stays in polling-fallback, does NOT escalate to closed", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    server.use(
      msw.get("/api/scan-runs/:id/events/", () =>
        new HttpResponse(null, { status: 500 }),
      ),
    );
    const { result } = await mountAndEnterFallback();
    for (let i = 0; i < 5; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
    }
    expect(result.current.status).toBe("polling-fallback");
    expect(result.current.events).toEqual([]);
    warn.mockRestore();
  });
});
