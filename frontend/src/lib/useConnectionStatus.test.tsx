import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../test/server";
import { makeRenderHookWrapper } from "../test/renderWithProviders";
import { useConnectionStatus } from "./useConnectionStatus";

describe("useConnectionStatus", () => {
  it("returns connected when /api/health/ is reachable and db is true", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({ status: "ok", db: true }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useConnectionStatus(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.connected).toBe(true));
  });

  it("returns disconnected when /api/health/ fails", async () => {
    server.use(msw.get("/api/health/", () => HttpResponse.error()));
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useConnectionStatus(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.connected).toBe(false));
  });

  it("returns disconnected when db: false", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({ status: "degraded", db: false }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useConnectionStatus(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.connected).toBe(false));
  });
});
