import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import { SCAN_RUNS_KEY, useScanRunTargetRunsQuery } from "./api";

describe("useScanRunTargetRunsQuery", () => {
  it("fetches page 1 by scan run id", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeScanTargetRun({ id: "tr-1" })],
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunTargetRunsQuery("r-1"),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.data?.count).toBe(1));
  });

  it("is disabled when scanRunId is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/:id/target-runs/", () => {
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
    renderHook(() => useScanRunTargetRunsQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });

  it("polls every 2s with livePolling: true", async () => {
    vi.useFakeTimers();
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
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
    renderHook(
      () => useScanRunTargetRunsQuery("r-1", { livePolling: true }),
      { wrapper: Wrapper },
    );
    await vi.advanceTimersByTimeAsync(2500);
    expect(calls).toBeGreaterThanOrEqual(2);
    vi.useRealTimers();
  });

  it.each([
    ["livePolling: false", { livePolling: false }],
    ["options omitted entirely", undefined],
  ] as const)("does NOT poll when %s", async (_, options) => {
    vi.useFakeTimers();
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
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
    renderHook(
      () => useScanRunTargetRunsQuery("r-1", options),
      { wrapper: Wrapper },
    );
    await vi.advanceTimersByTimeAsync(2500);
    expect(calls).toBe(1);
    vi.useRealTimers();
  });

  it("initial false → no flush on first render (only true→false edge fires the flush)", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
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
    renderHook(
      () => useScanRunTargetRunsQuery("r-1", { livePolling: false }),
      { wrapper: Wrapper },
    );
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(1); // one initial fetch, no flush invalidation
  });

  it("unmount mid-poll → no further MSW calls fire after unmount", async () => {
    vi.useFakeTimers();
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
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
    const { unmount } = renderHook(
      () => useScanRunTargetRunsQuery("r-1", { livePolling: true }),
      { wrapper: Wrapper },
    );
    await vi.advanceTimersByTimeAsync(2500);
    const beforeUnmount = calls;
    unmount();
    await vi.advanceTimersByTimeAsync(5000);
    expect(calls).toBe(beforeUnmount);
    vi.useRealTimers();
  });

  it("cascade refetch from SCAN_RUNS_KEY (paused parent, no polling)", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { Wrapper, client } = makeRenderHookWrapper();
    renderHook(
      () => useScanRunTargetRunsQuery("r-1", { livePolling: false }),
      { wrapper: Wrapper },
    );
    await new Promise((r) => setTimeout(r, 20)); // initial fetch
    const before = calls;
    await client.invalidateQueries({ queryKey: SCAN_RUNS_KEY });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(before + 1);
  });
});
