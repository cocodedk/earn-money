import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useTargetScanRunsQuery, TARGETS_KEY } from "./api";
import { makeScanRun } from "../scan-runs/__fixtures__/scan-run";

const TARGET_ID = "22222222-2222-2222-2222-222222222222";

describe("useTargetScanRunsQuery", () => {
  it("hits /api/scan-runs/?target=<id>", async () => {
    let calledWith = "";
    server.use(
      msw.get("/api/scan-runs/", ({ request }) => {
        calledWith = new URL(request.url).searchParams.get("target") ?? "";
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeScanRun({ id: "r-1" })],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetScanRunsQuery(TARGET_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(calledWith).toBe(TARGET_ID);
  });

  it("disabled when targetId is undefined", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/", () => {
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
    renderHook(() => useTargetScanRunsQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });

  it("cascades from TARGETS_KEY invalidation", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/", () => {
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
    renderHook(() => useTargetScanRunsQuery(TARGET_ID), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    const before = calls;
    await client.invalidateQueries({ queryKey: TARGETS_KEY });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(before + 1);
  });
});
