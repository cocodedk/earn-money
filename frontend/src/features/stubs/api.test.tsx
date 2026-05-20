import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { withBareArray } from "../../test/helpers";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { STUBS_KEY, useStubQuery, useStubsQuery } from "./api";
import { makeStub, makeStubWithBody } from "./__fixtures__/stub";

const STUB_SUMMARY = makeStub();

describe("useStubsQuery", () => {
  it("fetches a bare array and returns the list", async () => {
    withBareArray("/api/stubs/", [STUB_SUMMARY]);
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.length).toBe(1));
    expect(result.current.data?.[0].title).toBe("Framework detection");
  });
});

describe("useStubQuery", () => {
  it("fetches one stub including the markdown body", async () => {
    server.use(
      msw.get("/api/stubs/1.1/", () =>
        HttpResponse.json(makeStubWithBody({ body: "# 1.1\n\nbody text" })),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubQuery("1.1"), {
      wrapper: Wrapper,
    });
    await waitFor(() =>
      expect(result.current.data?.body).toContain("body text"),
    );
  });

  it("is disabled when slug is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/stubs/:slug/", () => {
        calls += 1;
        return HttpResponse.json(STUB_SUMMARY);
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubQuery(undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.isLoading).toBe(false);
    expect(calls).toBe(0);
  });

  it("exposes STUBS_KEY at the module level for cache lookups", () => {
    expect(STUBS_KEY).toEqual(["stubs"]);
  });
});
