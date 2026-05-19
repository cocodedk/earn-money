import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useEvidenceQuery, useEvidenceDetailQuery } from "./api";

const sampleEvidence = {
  id: "e1",
  scan_run: "r1",
  target: "t1",
  finding: "f1",
  source: "header.X-Powered-By",
  url: "https://dvwa.cocode.dk/",
  method: "GET",
  field: "X-Powered-By",
  matched_value: "PHP/7.4",
  raw_excerpt: "X-Powered-By: PHP/7.4",
  content_hash: "ab12",
  data: {},
  created_at: "2026-05-18T20:00:00.000000Z",
};

describe("useEvidenceQuery", () => {
  it("fetches unfiltered global list", async () => {
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useEvidenceQuery(), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(0));
  });

  it.each([
    ["project", "p1"],
    ["target", "t1"],
    ["scan_run", "r1"],
    ["finding", "f1"],
    ["source", "header.X-Powered-By"],
  ] as const)(
    "includes ?%s=%s in the querystring when set",
    async (key, value) => {
      let url: URL | null = null;
      server.use(
        msw.get("/api/evidence/", ({ request }) => {
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
        () => useEvidenceQuery({ [key]: value } as Record<string, string>),
        { wrapper: Wrapper },
      );
      await waitFor(() => expect(url).not.toBeNull());
      expect(url!.searchParams.get(key)).toBe(value);
    },
  );

  it("skips empty values", async () => {
    let url: URL | null = null;
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
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
    renderHook(() => useEvidenceQuery({ source: "" }), { wrapper: Wrapper });
    await waitFor(() => expect(url).not.toBeNull());
    expect(url!.searchParams.has("source")).toBe(false);
  });
});

describe("useEvidenceDetailQuery", () => {
  it("fetches by id", async () => {
    server.use(
      msw.get("/api/evidence/e1/", () => HttpResponse.json(sampleEvidence)),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useEvidenceDetailQuery("e1"), {
      wrapper: Wrapper,
    });
    await waitFor(() =>
      expect(result.current.data?.matched_value).toBe("PHP/7.4"),
    );
  });

  it("stays disabled when id is null", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useEvidenceDetailQuery(null), {
      wrapper: Wrapper,
    });
    expect(result.current.isFetching).toBe(false);
  });
});
