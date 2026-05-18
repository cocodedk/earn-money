import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useStubsQuery, useStubDetailQuery } from "./api";

const sampleStub = {
  slug: "1.1",
  phase: 1,
  spec: 1,
  title: "Framework detection",
  status: "done",
  fixture: "juiceshop",
  category: "information-gathering",
  phase_title: "Information gathering",
  phase_slug: "01-information-gathering",
  spec_slug: "01-framework-detection",
  path: "01-information-gathering/01-framework-detection.md",
};

describe("useStubsQuery", () => {
  it("fetches the unpaginated stub list", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.json([sampleStub])));
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.[0]?.slug).toBe("1.1"));
  });
});

describe("useStubDetailQuery", () => {
  it("fetches a stub by slug, including body", async () => {
    server.use(
      msw.get("/api/stubs/1.1/", () =>
        HttpResponse.json({ ...sampleStub, body: "# Framework detection\n\nDetect…" }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubDetailQuery("1.1"), {
      wrapper: Wrapper,
    });
    await waitFor(() =>
      expect(result.current.data?.body).toContain("Framework detection"),
    );
  });

  it("stays disabled when slug is null", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubDetailQuery(null), {
      wrapper: Wrapper,
    });
    expect(result.current.isFetching).toBe(false);
  });
});
