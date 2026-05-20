import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import {
  evidenceDetailKey,
  evidenceListKey,
  useEvidenceDetailQuery,
  useEvidenceListQuery,
} from "./api";
import { makeEvidence } from "../scan-runs/__fixtures__/evidence";
import { paged } from "./__fixtures__/refData";

const EVIDENCE_ID = "eeeeeeee-1111-1111-1111-111111111111";

describe("useEvidenceListQuery — URL composition", () => {
  it("omits query string when filters are empty", async () => {
    let calledWith: string | undefined;
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        calledWith = new URL(request.url).search;
        return HttpResponse.json(paged([makeEvidence()]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useEvidenceListQuery({}), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(calledWith).toBe("");
  });

  it("sends only the filters that are set (single filter)", async () => {
    let search = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useEvidenceListQuery({ source: "http-headers" }), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(search).not.toBe(""));
    expect(search).toBe("?source=http-headers");
  });

  it("ANDs every filter together in a stable order", async () => {
    let search = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () =>
        useEvidenceListQuery({
          project: "p-1",
          target: "t-1",
          scan_run: "sr-1",
          finding: "f-1",
          source: "http-headers",
        }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(search).not.toBe(""));
    const params = new URLSearchParams(search);
    expect(params.get("project")).toBe("p-1");
    expect(params.get("target")).toBe("t-1");
    expect(params.get("scan_run")).toBe("sr-1");
    expect(params.get("finding")).toBe("f-1");
    expect(params.get("source")).toBe("http-headers");
  });

  it("URL-encodes values that need it", async () => {
    let search = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () => useEvidenceListQuery({ source: "needs encoding" }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(search).not.toBe(""));
    expect(search).toContain("source=needs+encoding");
  });

  it("drops keys whose value is undefined", async () => {
    let search = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () =>
        useEvidenceListQuery({
          project: "p-1",
          target: undefined,
          source: undefined,
        }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(search).not.toBe(""));
    expect(search).toBe("?project=p-1");
  });
});

describe("useEvidenceListQuery — caching", () => {
  it("uses a stable query key derived from filters", () => {
    expect(evidenceListKey({ source: "x", project: "p-1" })).toEqual(
      evidenceListKey({ project: "p-1", source: "x" }),
    );
  });

  it("different filters produce different keys", () => {
    expect(evidenceListKey({ source: "a" })).not.toEqual(
      evidenceListKey({ source: "b" }),
    );
  });
});

describe("useEvidenceDetailQuery", () => {
  it("hits /api/evidence/<id>/ and returns the evidence", async () => {
    let path = "";
    server.use(
      msw.get(`/api/evidence/${EVIDENCE_ID}/`, ({ request }) => {
        path = new URL(request.url).pathname;
        return HttpResponse.json(makeEvidence({ id: EVIDENCE_ID }));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useEvidenceDetailQuery(EVIDENCE_ID),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.data?.id).toBe(EVIDENCE_ID));
    expect(path).toBe(`/api/evidence/${EVIDENCE_ID}/`);
  });

  it("is disabled when id is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/evidence/:id/", () => {
        calls += 1;
        return HttpResponse.json(makeEvidence());
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useEvidenceDetailQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });

  it("uses ['evidence','detail',id] as its query key", () => {
    expect(evidenceDetailKey(EVIDENCE_ID)).toEqual([
      "evidence",
      "detail",
      EVIDENCE_ID,
    ]);
  });
});
