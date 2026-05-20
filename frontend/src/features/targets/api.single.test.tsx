import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useTargetQuery } from "./api";

const TARGET_ID = "22222222-2222-2222-2222-222222222222";

describe("useTargetQuery", () => {
  it("fetches a single target by id", async () => {
    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () =>
        HttpResponse.json({
          id: TARGET_ID,
          project: "p-1",
          base_url: "https://dvwa.cocode.dk",
          host: "dvwa.cocode.dk",
          ip: null,
          status: "active",
          created_at: "2026-05-19T08:00:00.000000Z",
          updated_at: "2026-05-19T08:00:00.000000Z",
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetQuery(TARGET_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.id).toBe(TARGET_ID));
  });

  it("is disabled when id is undefined", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/targets/:id/", () => {
        calls += 1;
        return HttpResponse.json({});
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useTargetQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });
});
