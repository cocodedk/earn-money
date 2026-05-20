import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { installMockEventSource } from "../../test/sseMock";
import { makeEvent } from "./__fixtures__/event";
import { RUN_A, mountAndEnterFallback } from "./__fixtures__/sseTestHelpers";

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

describe("useScanRunEvents — polling fallback entry & ordering", () => {
  it("after 5 SSE failures → status polling-fallback, polls the events endpoint", async () => {
    let url = "";
    server.use(
      msw.get("/api/scan-runs/:id/events/", ({ request, params }) => {
        url = `/api/scan-runs/${params.id}/events/${new URL(request.url).search}`;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { result } = await mountAndEnterFallback();
    expect(result.current.status).toBe("polling-fallback");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(url).toBe(`/api/scan-runs/${RUN_A}/events/`);
  });

  it("polling tick appends events in created_at ascending order", async () => {
    server.use(
      msw.get("/api/scan-runs/:id/events/", () =>
        HttpResponse.json({
          count: 2,
          next: null,
          previous: null,
          results: [
            makeEvent({ id: "e1", created_at: "2026-05-20T08:00:00Z" }),
            makeEvent({ id: "e2", created_at: "2026-05-20T08:00:01Z" }),
          ],
        }),
      ),
    );
    const { result } = await mountAndEnterFallback();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.events.length).toBe(2);
    expect(result.current.events.map((e) => e.id)).toEqual(["e1", "e2"]);
  });
});
