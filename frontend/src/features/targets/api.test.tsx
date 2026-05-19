import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import {
  useTargetsQuery,
  useTargetDetailQuery,
  useCreateTargetMutation,
  TARGETS_KEY,
} from "./api";

describe("useTargetsQuery", () => {
  it("fetches targets filtered by project", async () => {
    let requestedUrl: URL | null = null;
    server.use(
      msw.get("/api/targets/", ({ request }) => {
        requestedUrl = new URL(request.url);
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "t1",
              project: "p1",
              base_url: "https://dvwa.cocode.dk",
              host: null,
              ip: null,
              status: "active",
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetsQuery("p1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(requestedUrl!.searchParams.get("project")).toBe("p1");
  });

  it("omits the project filter when projectId is null", async () => {
    let requestedUrl: URL | null = null;
    server.use(
      msw.get("/api/targets/", ({ request }) => {
        requestedUrl = new URL(request.url);
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useTargetsQuery(null), { wrapper: Wrapper });
    await waitFor(() => expect(requestedUrl).not.toBeNull());
    expect(requestedUrl!.searchParams.has("project")).toBe(false);
  });
});

describe("useCreateTargetMutation", () => {
  it("POSTs the body and invalidates targets + projects", async () => {
    let received: unknown = null;
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(
          {
            id: "t-new",
            project: "p1",
            base_url: "https://x",
            host: null,
            ip: null,
            status: "active",
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateTargetMutation(), {
      wrapper: Wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync({
        project: "p1",
        base_url: "https://x",
      });
    });
    expect(received).toMatchObject({ project: "p1", base_url: "https://x" });
    expect(spy).toHaveBeenCalledWith({ queryKey: TARGETS_KEY });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});

describe("useTargetDetailQuery", () => {
  it("fetches by id", async () => {
    server.use(
      msw.get("/api/targets/t1/", () =>
        HttpResponse.json({
          id: "t1",
          project: "p1",
          base_url: "https://dvwa.cocode.dk",
          host: null,
          ip: null,
          status: "active",
          created_at: "2026-05-18T20:00:00.000000Z",
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetDetailQuery("t1"), {
      wrapper: Wrapper,
    });
    await waitFor(() =>
      expect(result.current.data?.base_url).toBe("https://dvwa.cocode.dk"),
    );
  });

  it("stays disabled when id is null", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetDetailQuery(null), {
      wrapper: Wrapper,
    });
    expect(result.current.isFetching).toBe(false);
  });
});
