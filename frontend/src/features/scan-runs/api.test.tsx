import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import {
  useScanRunsQuery,
  useScanRunDetailQuery,
  useCreateScanRunMutation,
  useScanRunLifecycleMutation,
  SCAN_RUNS_KEY,
} from "./api";

const sampleScanRun = {
  id: "r1",
  project: "p1",
  stub_slug: "1.1",
  status: "queued",
  target_run_count: 0,
  findings_count: 0,
  started_at: null,
  finished_at: null,
  created_at: "2026-05-18T20:00:00.000000Z",
};

describe("useScanRunsQuery", () => {
  it("fetches with project filter", async () => {
    let url: URL | null = null;
    server.use(
      msw.get("/api/scan-runs/", ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useScanRunsQuery({ project: "p1" }), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(url).not.toBeNull());
    expect(url!.searchParams.get("project")).toBe("p1");
  });

  it("emits no query string when filter is empty", async () => {
    let url: URL | null = null;
    server.use(
      msw.get("/api/scan-runs/", ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useScanRunsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(url).not.toBeNull());
    expect(url!.search).toBe("");
  });

  it("includes status + stub_slug filters when given", async () => {
    let url: URL | null = null;
    server.use(
      msw.get("/api/scan-runs/", ({ request }) => {
        url = new URL(request.url);
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
      () => useScanRunsQuery({ status: "running", stub_slug: "1.1" }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(url).not.toBeNull());
    expect(url!.searchParams.get("status")).toBe("running");
    expect(url!.searchParams.get("stub_slug")).toBe("1.1");
  });
});

describe("useScanRunDetailQuery", () => {
  it("fetches by id", async () => {
    server.use(
      msw.get("/api/scan-runs/r1/", () => HttpResponse.json(sampleScanRun)),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useScanRunDetailQuery("r1"), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.id).toBe("r1"));
  });

  it("stays disabled when id is null", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useScanRunDetailQuery(null), {
      wrapper: Wrapper,
    });
    expect(result.current.isFetching).toBe(false);
  });
});

describe("useCreateScanRunMutation", () => {
  it("POSTs and invalidates scan-runs + projects", async () => {
    server.use(
      msw.post("/api/scan-runs/", () =>
        HttpResponse.json(sampleScanRun, { status: 201 }),
      ),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateScanRunMutation(), {
      wrapper: Wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync({
        project: "p1",
        stub_slug: "1.1",
        target_ids: ["t1"],
      });
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: SCAN_RUNS_KEY });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});

describe("useScanRunLifecycleMutation", () => {
  it("POSTs to the action endpoint and invalidates detail", async () => {
    let posted = false;
    server.use(
      msw.post("/api/scan-runs/r1/start/", () => {
        posted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useScanRunLifecycleMutation("r1"), {
      wrapper: Wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync("start");
    });
    expect(posted).toBe(true);
    expect(spy).toHaveBeenCalledWith({ queryKey: [...SCAN_RUNS_KEY, "r1"] });
  });
});
