import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../test/server";
import { makeRenderHookWrapper } from "../test/renderWithProviders";
import { useSystemHealth } from "./useConnectionStatus";

describe("useSystemHealth", () => {
  it("returns the full health response shape", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({
          status: "ok",
          db: true,
          redis: true,
          worker: true,
          version: "1.2.3",
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useSystemHealth(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.status).toBe("ok"));
    expect(result.current.data).toEqual({
      status: "ok",
      db: true,
      redis: true,
      worker: true,
      version: "1.2.3",
    });
  });

  it("exposes error state when /api/health/ fails", async () => {
    server.use(msw.get("/api/health/", () => HttpResponse.error()));
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useSystemHealth(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("exposes a degraded backend response shape", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({
          status: "degraded",
          db: false,
          redis: false,
          worker: true,
          version: "1.2.3",
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useSystemHealth(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.status).toBe("degraded"));
    expect(result.current.data?.db).toBe(false);
    expect(result.current.data?.worker).toBe(true);
  });
});
