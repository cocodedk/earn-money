import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useTargetEventsQuery } from "./api";
import { makeEvent } from "../scan-runs/__fixtures__/event";

const TARGET_ID = "22222222-2222-2222-2222-222222222222";

describe("useTargetEventsQuery", () => {
  it("hits /api/events/?target=<id>", async () => {
    let calledWith = "";
    server.use(
      msw.get("/api/events/", ({ request }) => {
        calledWith = new URL(request.url).searchParams.get("target") ?? "";
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeEvent()],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetEventsQuery(TARGET_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(calledWith).toBe(TARGET_ID);
  });

  it("disabled when targetId is undefined", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/events/", () => {
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
    renderHook(() => useTargetEventsQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });
});
