import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../../test/server";
import { makeTestQueryClient } from "../../test/renderWithProviders";
import { useProjectsQuery, useCreateProjectMutation, PROJECTS_KEY } from "./api";

function makeWrapper() {
  const client = makeTestQueryClient();
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return { client, Wrapper };
}

describe("useProjectsQuery", () => {
  it("fetches and returns the page of projects", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "u1",
              name: "Local Lab",
              description: "",
              target_count: 3,
              scan_run_count: 0,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useProjectsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(result.current.data?.results[0].name).toBe("Local Lab");
  });
});

describe("useCreateProjectMutation", () => {
  it("POSTs the body and invalidates the projects list", async () => {
    let received: unknown = null;
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.post("/api/projects/", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(
          {
            id: "u-new",
            name: "Local Lab",
            description: "lab",
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    const { client, Wrapper } = makeWrapper();
    const listSpy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateProjectMutation(), {
      wrapper: Wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync({ name: "Local Lab", description: "lab" });
    });
    expect(received).toEqual({ name: "Local Lab", description: "lab" });
    expect(listSpy).toHaveBeenCalledWith({ queryKey: PROJECTS_KEY });
  });
});
