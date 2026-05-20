import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeScanRun } from "./__fixtures__/scan-run";
import type { ScanRunStatus } from "../../types/api";
import { useScanRunQuery } from "./api";

describe("useScanRunQuery self-polling", () => {
  it.each(["running", "stopping"] as const)(
    "polls every 2s while status is %s",
    async (status) => {
      vi.useFakeTimers();
      let calls = 0;
      server.use(
        msw.get("/api/scan-runs/r-1/", () => {
          calls += 1;
          return HttpResponse.json(makeScanRun({ id: "r-1", status }));
        }),
      );
      const { Wrapper } = makeRenderHookWrapper();
      renderHook(() => useScanRunQuery("r-1"), { wrapper: Wrapper });
      await vi.advanceTimersByTimeAsync(2500);
      expect(calls).toBeGreaterThanOrEqual(2);
      vi.useRealTimers();
    },
  );

  it.each(["queued", "paused", "done", "failed", "stopped"] as const)(
    "does NOT poll when status is %s",
    async (status) => {
      vi.useFakeTimers();
      let calls = 0;
      server.use(
        msw.get("/api/scan-runs/r-1/", () => {
          calls += 1;
          return HttpResponse.json(makeScanRun({ id: "r-1", status }));
        }),
      );
      const { Wrapper } = makeRenderHookWrapper();
      renderHook(() => useScanRunQuery("r-1"), { wrapper: Wrapper });
      await vi.advanceTimersByTimeAsync(2500);
      expect(calls).toBe(1);
      vi.useRealTimers();
    },
  );

  it("stops polling on running → done transition", async () => {
    vi.useFakeTimers();
    let calls = 0;
    let status: ScanRunStatus = "running";
    server.use(
      msw.get("/api/scan-runs/r-1/", () => {
        calls += 1;
        return HttpResponse.json(makeScanRun({ id: "r-1", status }));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useScanRunQuery("r-1"), { wrapper: Wrapper });
    await vi.advanceTimersByTimeAsync(2500); // poll fires while running
    status = "done";
    await vi.advanceTimersByTimeAsync(2500); // catches done
    const afterDone = calls;
    await vi.advanceTimersByTimeAsync(5000); // no more polls
    expect(calls).toBe(afterDone);
    vi.useRealTimers();
  });
});
