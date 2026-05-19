import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse, delay } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import { useScanRunTargetRunsQuery } from "./api";

describe("useScanRunTargetRunsQuery — terminal flush", () => {
  it("no-in-flight branch: cache ends with fresh post-flush rows", async () => {
    vi.useFakeTimers();
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            makeScanTargetRun({
              id: "tr-1",
              status: phase === "pre" ? "running" : "done",
            }),
          ],
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { rerender, result } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunTargetRunsQuery("r-1", { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await vi.advanceTimersByTimeAsync(2500); // poll settles with "running"
    phase = "post";
    rerender({ live: false }); // terminal flush fires
    await vi.advanceTimersByTimeAsync(50);
    vi.useRealTimers();
    await waitFor(() =>
      expect(result.current.data?.results[0].status).toBe("done"),
    );
  });

  it("in-flight with cached data: cache ends fresh", async () => {
    vi.useFakeTimers();
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", async () => {
        if (phase === "pre") {
          return HttpResponse.json({
            count: 1,
            next: null,
            previous: null,
            results: [makeScanTargetRun({ id: "tr-1", status: "running" })],
          });
        }
        await delay(200); // simulate in-flight
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: "done" })],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { rerender, result } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunTargetRunsQuery("r-1", { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await vi.advanceTimersByTimeAsync(2500); // cached
    phase = "post";
    await vi.advanceTimersByTimeAsync(2000); // next poll fires (in-flight)
    rerender({ live: false }); // flush during in-flight
    await vi.advanceTimersByTimeAsync(500);
    vi.useRealTimers();
    await waitFor(() =>
      expect(result.current.data?.results[0].status).toBe("done"),
    );
  });

  it("no-cached-data in-flight: cache ends fresh (round-5 edge case)", async () => {
    vi.useFakeTimers();
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", async () => {
        if (phase === "pre") {
          await delay(500); // initial fetch still pending
          return HttpResponse.json({
            count: 1,
            next: null,
            previous: null,
            results: [makeScanTargetRun({ id: "tr-1", status: "running" })],
          });
        }
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: "done" })],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { rerender, result } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunTargetRunsQuery("r-1", { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await vi.advanceTimersByTimeAsync(100); // initial fetch in flight, no cached data
    phase = "post";
    rerender({ live: false }); // terminal flush during initial-fetch in-flight
    await vi.advanceTimersByTimeAsync(500);
    vi.useRealTimers();
    await waitFor(() =>
      expect(result.current.data?.results[0].status).toBe("done"),
    );
  });
});
