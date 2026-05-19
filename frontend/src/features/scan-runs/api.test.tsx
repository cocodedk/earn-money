import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { withPaginated } from "../../test/helpers";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeScanRun } from "./__fixtures__/scan-run";
import {
  SCAN_RUNS_KEY,
  useCreateScanRunMutation,
  usePauseScanRunMutation,
  useResumeScanRunMutation,
  useScanRunsQuery,
  useStartScanRunMutation,
  useStopScanRunMutation,
} from "./api";

describe("useScanRunsQuery", () => {
  it("fetches the paginated list", async () => {
    withPaginated("/api/scan-runs/", [makeScanRun()]);
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useScanRunsQuery(), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(result.current.data?.results[0].stub_slug).toBe("1.1");
  });
});

describe("useCreateScanRunMutation", () => {
  it("POSTs the body and invalidates SCAN_RUNS_KEY", async () => {
    let received: unknown = null;
    server.use(
      msw.post("/api/scan-runs/", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(makeScanRun(), { status: 201 });
      }),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateScanRunMutation(), {
      wrapper: Wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync({
        project: "p-1",
        stub_slug: "1.1",
        target_ids: ["t-1"],
      });
    });
    expect(received).toEqual({
      project: "p-1",
      stub_slug: "1.1",
      target_ids: ["t-1"],
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: SCAN_RUNS_KEY });
  });
});

describe("lifecycle mutations", () => {
  const cases = [
    {
      name: "start",
      useHook: useStartScanRunMutation,
      path: "/api/scan-runs/r-1/start/",
    },
    {
      name: "pause",
      useHook: usePauseScanRunMutation,
      path: "/api/scan-runs/r-1/pause/",
    },
    {
      name: "resume",
      useHook: useResumeScanRunMutation,
      path: "/api/scan-runs/r-1/resume/",
    },
    {
      name: "stop",
      useHook: useStopScanRunMutation,
      path: "/api/scan-runs/r-1/stop/",
    },
  ] as const;

  it.each(cases)(
    "$name POSTs the right URL and invalidates the cache",
    async ({ useHook, path }) => {
      let hit = false;
      server.use(
        msw.post(path, () => {
          hit = true;
          return HttpResponse.json(makeScanRun({ status: "running" }));
        }),
      );
      const { client, Wrapper } = makeRenderHookWrapper();
      const spy = vi.spyOn(client, "invalidateQueries");
      const { result } = renderHook(() => useHook(), { wrapper: Wrapper });
      await act(async () => {
        await result.current.mutateAsync("r-1");
      });
      expect(hit).toBe(true);
      expect(spy).toHaveBeenCalledWith({ queryKey: SCAN_RUNS_KEY });
    },
  );
});
