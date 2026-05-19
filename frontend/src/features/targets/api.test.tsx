import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../../test/server";
import { TARGETS_KEY, useCreateTargetMutation, useTargetsQuery } from "./api";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return { client, Wrapper };
}

describe("useTargetsQuery", () => {
  it("fetches and returns the page of targets", async () => {
    server.use(
      msw.get("/api/targets/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "t-1",
              project: "p-1",
              base_url: "https://dvwa.cocode.dk",
              host: "dvwa.cocode.dk",
              ip: null,
              status: "active",
              created_at: "2026-05-19T08:00:00.000000Z",
              updated_at: "2026-05-19T08:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useTargetsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(result.current.data?.results[0].host).toBe("dvwa.cocode.dk");
  });
});

describe("useCreateTargetMutation", () => {
  it("POSTs the body and invalidates the targets list", async () => {
    let received: unknown = null;
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(
          {
            id: "t-new",
            project: "p-1",
            base_url: "https://dvwa.cocode.dk",
            host: "dvwa.cocode.dk",
            ip: null,
            status: "active",
            created_at: "2026-05-19T08:00:00.000000Z",
            updated_at: "2026-05-19T08:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    const { client, Wrapper } = makeWrapper();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateTargetMutation(), {
      wrapper: Wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync({
        project: "p-1",
        base_url: "https://dvwa.cocode.dk",
      });
    });
    expect(received).toEqual({
      project: "p-1",
      base_url: "https://dvwa.cocode.dk",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: TARGETS_KEY });
  });
});
