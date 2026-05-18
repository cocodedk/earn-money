import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../test/server";
import { useCurrentProject } from "./useCurrentProject";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function noProjects() {
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("useCurrentProject", () => {
  it("starts null when localStorage is empty", () => {
    noProjects();
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    expect(result.current.id).toBeNull();
  });

  it("persists setId to localStorage and reflects in next read", () => {
    noProjects();
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    act(() => result.current.setId("u-1"));
    expect(window.localStorage.getItem("em.frontend.currentProjectId")).toBe(
      "u-1",
    );
    expect(result.current.id).toBe("u-1");
  });

  it("removes the key when setId is called with null", () => {
    noProjects();
    window.localStorage.setItem("em.frontend.currentProjectId", "u-1");
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    act(() => result.current.setId(null));
    expect(
      window.localStorage.getItem("em.frontend.currentProjectId"),
    ).toBeNull();
  });

  it("resolves the project from the cached list", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "u-1",
              name: "Local Lab",
              description: "",
              target_count: 0,
              scan_run_count: 0,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    window.localStorage.setItem("em.frontend.currentProjectId", "u-1");
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    await waitFor(() => expect(result.current.project?.name).toBe("Local Lab"));
  });

  it("clears the id when the project no longer exists", async () => {
    noProjects();
    window.localStorage.setItem("em.frontend.currentProjectId", "u-gone");
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    await waitFor(() => expect(result.current.id).toBeNull());
    expect(
      window.localStorage.getItem("em.frontend.currentProjectId"),
    ).toBeNull();
  });
});
