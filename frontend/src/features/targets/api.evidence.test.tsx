import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useTargetEvidenceQuery } from "./api";
import { makeEvidence } from "../scan-runs/__fixtures__/evidence";

const TARGET_ID = "22222222-2222-2222-2222-222222222222";

describe("useTargetEvidenceQuery", () => {
  it("hits /api/evidence/?target=<id>", async () => {
    let calledWith = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        calledWith = new URL(request.url).searchParams.get("target") ?? "";
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeEvidence()],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetEvidenceQuery(TARGET_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(calledWith).toBe(TARGET_ID);
  });

  it("disabled when targetId is undefined", async () => {
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
    renderHook(() => useTargetEvidenceQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });
});
