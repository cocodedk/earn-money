import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { MockEventSource, installMockEventSource } from "../../test/sseMock";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeEvent } from "./__fixtures__/event";
import {
  RUN_A,
  flushReactUpdates,
  lastInstance,
  mountAndEnterFallback,
  waitConnected,
} from "./__fixtures__/sseTestHelpers";
import { useScanRunEvents } from "./useScanRunEvents";

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

const DELAYS = [1000, 2000, 4000, 8000, 16000];

describe("useScanRunEvents — polling fallback lifecycle", () => {
  it("livePolling=false while polling → status closed, polling stops", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/:id/events/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result, rerender } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunEvents(RUN_A, { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await waitConnected(result);
    vi.useFakeTimers();
    MockEventSource.autoOpen = false;
    for (let i = 0; i < DELAYS.length; i += 1) {
      act(() => lastInstance().fail());
      await flushReactUpdates();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(DELAYS[i]);
      });
    }
    act(() => lastInstance().fail());
    await flushReactUpdates();
    expect(result.current.status).toBe("polling-fallback");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    const before = calls;
    rerender({ live: false });
    await flushReactUpdates();
    expect(result.current.status).toBe("closed");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(calls).toBe(before);
  });

  it("unmount while polling stops the loop — no more fetches", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/:id/events/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { result, unmount } = await mountAndEnterFallback();
    expect(result.current.status).toBe("polling-fallback");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    const before = calls;
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(calls).toBe(before);
  });

  it("clear() while polling empties buffer; next request sends NO Last-Event-ID", async () => {
    const seenHeaders: (string | null)[] = [];
    let phase: "first" | "second" = "first";
    server.use(
      msw.get("/api/scan-runs/:id/events/", ({ request }) => {
        seenHeaders.push(request.headers.get("Last-Event-ID"));
        if (phase === "first") {
          return HttpResponse.json({
            count: 1,
            next: null,
            previous: null,
            results: [makeEvent({ id: "e1" })],
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
    expect(result.current.events.length).toBe(1);
    phase = "second";
    act(() => result.current.clear());
    expect(result.current.events).toEqual([]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(seenHeaders[seenHeaders.length - 1]).toBeNull();
    expect(result.current.status).toBe("polling-fallback");
  });

  it("livePolling false→true mid-fallback exits polling; SSE takes over fresh", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/:id/events/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result, rerender } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunEvents(RUN_A, { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await waitConnected(result);
    vi.useFakeTimers();
    MockEventSource.autoOpen = false;
    for (let i = 0; i < DELAYS.length; i += 1) {
      act(() => lastInstance().fail());
      await flushReactUpdates();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(DELAYS[i]);
      });
    }
    act(() => lastInstance().fail());
    await flushReactUpdates();
    expect(result.current.status).toBe("polling-fallback");
    rerender({ live: false });
    await flushReactUpdates();
    expect(result.current.status).toBe("closed");
    const before = calls;
    rerender({ live: true });
    await flushReactUpdates();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(calls).toBe(before);
  });
});
