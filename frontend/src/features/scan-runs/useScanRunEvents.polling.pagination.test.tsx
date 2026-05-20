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

function eventBatch(start: number, end: number) {
  const out = [];
  for (let i = start; i <= end; i += 1) {
    out.push(
      makeEvent({
        id: `e${i}`,
        created_at: `2026-05-20T08:00:${String(i).padStart(2, "0")}Z`,
      }),
    );
  }
  return out;
}

describe("useScanRunEvents — polling fallback pagination drain", () => {
  it("fetches next page within same tick when next != null", async () => {
    let pageOneCalls = 0;
    let pageTwoCalls = 0;
    server.use(
      msw.get("/api/events-page-2/", () => {
        pageTwoCalls += 1;
        return HttpResponse.json({
          count: 4,
          next: null,
          previous: null,
          results: [
            makeEvent({ id: "e3", created_at: "2026-05-20T08:00:02Z" }),
            makeEvent({ id: "e4", created_at: "2026-05-20T08:00:03Z" }),
          ],
        });
      }),
      msw.get("/api/scan-runs/:id/events/", () => {
        pageOneCalls += 1;
        return HttpResponse.json({
          count: 4,
          next: `/api/events-page-2/`,
          previous: null,
          results: [
            makeEvent({ id: "e1", created_at: "2026-05-20T08:00:00Z" }),
            makeEvent({ id: "e2", created_at: "2026-05-20T08:00:01Z" }),
          ],
        });
      }),
    );
    const { result } = await mountAndEnterFallback();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events.length).toBe(4);
    expect(result.current.events.map((e) => e.id)).toEqual([
      "e1",
      "e2",
      "e3",
      "e4",
    ]);
    expect(pageOneCalls).toBe(1);
    expect(pageTwoCalls).toBe(1);
  });

  it("soft buffer cap during drain — keeps newest maxBuffer across pages", async () => {
    server.use(
      msw.get("/api/events-page-2/", () =>
        HttpResponse.json({
          count: 15,
          next: null,
          previous: null,
          results: eventBatch(8, 15),
        }),
      ),
      msw.get("/api/scan-runs/:id/events/", () =>
        HttpResponse.json({
          count: 15,
          next: `/api/events-page-2/`,
          previous: null,
          results: eventBatch(1, 7),
        }),
      ),
    );
    const { result } = await mountAndEnterFallback({ maxBuffer: 10 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events.length).toBe(10);
    expect(result.current.events.map((e) => e.id)).toEqual([
      "e6",
      "e7",
      "e8",
      "e9",
      "e10",
      "e11",
      "e12",
      "e13",
      "e14",
      "e15",
    ]);
  });
});
