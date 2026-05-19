import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useFindingsQuery, useFindingDetailQuery } from "./api";

const sampleFinding = {
  id: "f1",
  scan_run: "r1",
  target: "t1",
  stub_slug: "1.1",
  title: "Express detected",
  category: "framework-detection",
  severity: "info",
  confidence: "high",
  status: "candidate",
  data: { technology: "Express" },
  created_at: "2026-05-18T20:00:00.000000Z",
  updated_at: "2026-05-18T20:00:00.000000Z",
};

describe("useFindingsQuery", () => {
  it("fetches unfiltered global list", async () => {
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingsQuery(), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(0));
  });

  it.each([
    ["project", "p1"],
    ["target", "t1"],
    ["scan_run", "r1"],
    ["stub", "1.1"],
    ["severity", "high"],
    ["confidence", "medium"],
    ["status", "candidate"],
  ] as const)(
    "includes ?%s=%s in the querystring when set",
    async (key, value) => {
      let url: URL | null = null;
      server.use(
        msw.get("/api/findings/", ({ request }) => {
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
        () => useFindingsQuery({ [key]: value } as Record<string, string>),
        { wrapper: Wrapper },
      );
      await waitFor(() => expect(url).not.toBeNull());
      expect(url!.searchParams.get(key)).toBe(value);
    },
  );

  it("skips keys whose value is empty string", async () => {
    let url: URL | null = null;
    server.use(
      msw.get("/api/findings/", ({ request }) => {
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
    renderHook(() => useFindingsQuery({ stub: "" }), { wrapper: Wrapper });
    await waitFor(() => expect(url).not.toBeNull());
    expect(url!.searchParams.has("stub")).toBe(false);
  });
});

describe("useFindingDetailQuery", () => {
  it("fetches by id", async () => {
    server.use(
      msw.get("/api/findings/f1/", () => HttpResponse.json(sampleFinding)),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingDetailQuery("f1"), {
      wrapper: Wrapper,
    });
    await waitFor(() =>
      expect(result.current.data?.title).toBe("Express detected"),
    );
  });

  it("stays disabled when id is null", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingDetailQuery(null), {
      wrapper: Wrapper,
    });
    expect(result.current.isFetching).toBe(false);
  });
});
