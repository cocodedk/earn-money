import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../test/server";
import { useConnectionStatus } from "./useConnectionStatus";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useConnectionStatus", () => {
  it("returns connected when /api/health/ is reachable and db is true", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({ status: "ok", db: true }),
      ),
    );
    const { result } = renderHook(() => useConnectionStatus(), { wrapper });
    await waitFor(() => expect(result.current.connected).toBe(true));
  });

  it("returns disconnected when /api/health/ fails", async () => {
    server.use(msw.get("/api/health/", () => HttpResponse.error()));
    const { result } = renderHook(() => useConnectionStatus(), { wrapper });
    await waitFor(() => expect(result.current.connected).toBe(false));
  });

  it("returns disconnected when db: false", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({ status: "degraded", db: false }),
      ),
    );
    const { result } = renderHook(() => useConnectionStatus(), { wrapper });
    await waitFor(() => expect(result.current.connected).toBe(false));
  });
});
