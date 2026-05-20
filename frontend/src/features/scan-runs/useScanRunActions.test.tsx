import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeScanRun } from "./__fixtures__/scan-run";
import { useScanRunActions, VALID_ACTIONS } from "./useScanRunActions";
import type { LifecycleAction, ScanRunStatus } from "../../types/api";

const STATUSES: ScanRunStatus[] = [
  "queued",
  "running",
  "paused",
  "stopping",
  "stopped",
  "failed",
  "done",
];

describe("useScanRunActions — visibleActions", () => {
  it.each(STATUSES)("matches VALID_ACTIONS[%s]", (status) => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunActions(makeScanRun({ status })),
      { wrapper: Wrapper },
    );
    expect(result.current.visibleActions).toEqual(VALID_ACTIONS[status]);
  });
});

describe("useScanRunActions — handlers", () => {
  const cases: Array<{ action: LifecycleAction; path: string }> = [
    { action: "start", path: "/api/scan-runs/r-1/start/" },
    { action: "pause", path: "/api/scan-runs/r-1/pause/" },
    { action: "resume", path: "/api/scan-runs/r-1/resume/" },
    { action: "stop", path: "/api/scan-runs/r-1/stop/" },
  ];

  it.each(cases)("$action POSTs to $path", async ({ action, path }) => {
    let hit = false;
    server.use(
      msw.post(path, () => {
        hit = true;
        return HttpResponse.json(makeScanRun({ status: "running" }));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunActions(makeScanRun()),
      { wrapper: Wrapper },
    );
    result.current.handlers[action]();
    await waitFor(() => expect(hit).toBe(true));
  });
});
