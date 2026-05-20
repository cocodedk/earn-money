import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useScanRunEvidenceQuery, SCAN_RUNS_KEY } from "./api";
import { makeEvidence } from "./__fixtures__/evidence";

const SCAN_RUN_ID = "11111111-1111-1111-1111-111111111111";

describe("useScanRunEvidenceQuery", () => {
  it("hits /api/evidence/?scan_run=<id>", async () => {
    let calledWith = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        calledWith = new URL(request.url).searchParams.get("scan_run") ?? "";
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeEvidence()],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvidenceQuery(SCAN_RUN_ID, { livePolling: false }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(calledWith).toBe(SCAN_RUN_ID);
  });

  it("polls every 2s with livePolling: true", async () => {
    vi.useFakeTimers();
    let calls = 0;
    server.use(
      msw.get("/api/evidence/", () => {
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
      () => useScanRunEvidenceQuery(SCAN_RUN_ID, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await vi.advanceTimersByTimeAsync(2500);
    expect(calls).toBeGreaterThanOrEqual(2);
    vi.useRealTimers();
  });

  it("does NOT poll when livePolling: false", async () => {
    vi.useFakeTimers();
    let calls = 0;
    server.use(
      msw.get("/api/evidence/", () => {
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
      () => useScanRunEvidenceQuery(SCAN_RUN_ID, { livePolling: false }),
      { wrapper: Wrapper },
    );
    await vi.advanceTimersByTimeAsync(2500);
    expect(calls).toBe(1);
    vi.useRealTimers();
  });

  it("flush — no in-flight: cache ends with fresh post-flush rows", async () => {
    vi.useFakeTimers();
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            makeEvidence({
              id: "eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              source: phase === "pre" ? "v1-source" : "v2-source",
            }),
          ],
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { rerender, result } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunEvidenceQuery(SCAN_RUN_ID, { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await vi.advanceTimersByTimeAsync(2500);
    phase = "post";
    rerender({ live: false });
    await vi.advanceTimersByTimeAsync(50);
    vi.useRealTimers();
    await waitFor(() =>
      expect(result.current.data?.results[0].source).toBe("v2-source"),
    );
  });

  it("disabled when scanRunId is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/evidence/", () => {
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
      () => useScanRunEvidenceQuery(undefined, { livePolling: false }),
      { wrapper: Wrapper },
    );
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });

  it("cascades from SCAN_RUNS_KEY invalidation (key is child of SCAN_RUNS_KEY)", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/evidence/", () => {
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
      () => useScanRunEvidenceQuery(SCAN_RUN_ID, { livePolling: false }),
      { wrapper: Wrapper },
    );
    await new Promise((r) => setTimeout(r, 20));
    const before = calls;
    await client.invalidateQueries({ queryKey: SCAN_RUNS_KEY });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(before + 1);
  });
});
