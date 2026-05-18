import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ConnectionPill } from "./ConnectionPill";

function renderPill() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ConnectionPill />
    </QueryClientProvider>,
  );
}

describe("ConnectionPill", () => {
  it("shows Connected when /api/health/ is healthy", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({ status: "ok", db: true }),
      ),
    );
    renderPill();
    await waitFor(() => {
      expect(screen.getByTestId("connection-pill")).toHaveAttribute(
        "data-connected",
        "true",
      );
    });
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows Disconnected on health failure", async () => {
    server.use(msw.get("/api/health/", () => HttpResponse.error()));
    renderPill();
    await waitFor(() => {
      expect(screen.getByTestId("connection-pill")).toHaveAttribute(
        "data-connected",
        "false",
      );
    });
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });
});
