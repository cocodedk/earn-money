import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import {
  findingDetailKey,
  findingsListKey,
  useFindingDetailQuery,
  useFindingsListQuery,
} from "./api";
import { makeFinding } from "../scan-runs/__fixtures__/finding";
import { paged } from "./__fixtures__/refData";

const FINDING_ID = "ffffffff-1111-1111-1111-111111111111";

describe("useFindingsListQuery — URL composition", () => {
  it("omits query string when filters are empty", async () => {
    let calledWith: string | undefined;
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        calledWith = new URL(request.url).search;
        return HttpResponse.json(paged([makeFinding()]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingsListQuery({}), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(calledWith).toBe("");
  });

  it("sends only the filters that are set (single filter)", async () => {
    let search = "";
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useFindingsListQuery({ severity: "high" }), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(search).not.toBe(""));
    expect(search).toBe("?severity=high");
  });

  it("ANDs every filter together in a stable order", async () => {
    let search = "";
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () =>
        useFindingsListQuery({
          project: "p-1",
          target: "t-1",
          scan_run: "sr-1",
          stub_slug: "1.2-tls",
          severity: "medium",
          confidence: "high",
          status: "confirmed",
        }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(search).not.toBe(""));
    const params = new URLSearchParams(search);
    expect(params.get("project")).toBe("p-1");
    expect(params.get("target")).toBe("t-1");
    expect(params.get("scan_run")).toBe("sr-1");
    expect(params.get("stub_slug")).toBe("1.2-tls");
    expect(params.get("severity")).toBe("medium");
    expect(params.get("confidence")).toBe("high");
    expect(params.get("status")).toBe("confirmed");
  });

  it("URL-encodes values that need it", async () => {
    let search = "";
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () => useFindingsListQuery({ stub_slug: "1.2 with space" }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(search).not.toBe(""));
    expect(search).toContain("stub_slug=1.2+with+space");
  });

  it("drops keys whose value is undefined", async () => {
    let search = "";
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () =>
        useFindingsListQuery({
          project: "p-1",
          target: undefined,
          severity: undefined,
        }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(search).not.toBe(""));
    expect(search).toBe("?project=p-1");
  });
});

describe("useFindingsListQuery — caching", () => {
  it("uses a stable query key derived from filters", () => {
    expect(findingsListKey({ severity: "high", project: "p-1" })).toEqual(
      findingsListKey({ project: "p-1", severity: "high" }),
    );
  });

  it("different filters produce different keys", () => {
    expect(findingsListKey({ severity: "high" })).not.toEqual(
      findingsListKey({ severity: "low" }),
    );
  });
});

describe("useFindingDetailQuery", () => {
  it("hits /api/findings/<id>/ and returns the finding", async () => {
    let path = "";
    server.use(
      msw.get(`/api/findings/${FINDING_ID}/`, ({ request }) => {
        path = new URL(request.url).pathname;
        return HttpResponse.json(makeFinding({ id: FINDING_ID }));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingDetailQuery(FINDING_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.id).toBe(FINDING_ID));
    expect(path).toBe(`/api/findings/${FINDING_ID}/`);
  });

  it("is disabled when id is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/findings/:id/", () => {
        calls += 1;
        return HttpResponse.json(makeFinding());
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useFindingDetailQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });

  it("uses ['findings','detail',id] as its query key", () => {
    expect(findingDetailKey(FINDING_ID)).toEqual([
      "findings",
      "detail",
      FINDING_ID,
    ]);
  });
});

