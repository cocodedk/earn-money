import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { findingEvidenceKey, useFindingEvidenceQuery } from "./api";
import { makeEvidence } from "../scan-runs/__fixtures__/evidence";
import { paged } from "./__fixtures__/refData";

const FINDING_ID = "ffffffff-1111-1111-1111-111111111111";

describe("useFindingEvidenceQuery", () => {
  it("hits /api/evidence/?finding=<id>", async () => {
    let search = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(
          paged([makeEvidence({ finding: FINDING_ID })]),
        );
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingEvidenceQuery(FINDING_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(search).toBe(`?finding=${FINDING_ID}`);
  });

  it("is disabled when id is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/evidence/", () => {
        calls += 1;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useFindingEvidenceQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });

  it("uses ['findings','evidence',id] as its query key", () => {
    expect(findingEvidenceKey(FINDING_ID)).toEqual([
      "findings",
      "evidence",
      FINDING_ID,
    ]);
  });
});
