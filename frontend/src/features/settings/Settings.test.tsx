import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { Settings } from "./Settings";

describe("Settings page", () => {
  it("renders all six status rows from the /api/health/ response", async () => {
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
    renderWithProviders(<Settings />);
    expect(await screen.findByText("Settings")).toBeInTheDocument();
    expect(await screen.findByTestId("settings-backend-status")).toHaveTextContent("ok");
    expect(await screen.findByTestId("settings-db-status")).toHaveTextContent("up");
    expect(await screen.findByTestId("settings-redis-status")).toHaveTextContent("up");
    expect(await screen.findByTestId("settings-worker-status")).toHaveTextContent("up");
    expect(await screen.findByTestId("settings-backend-version")).toHaveTextContent("1.2.3");
    expect(await screen.findByTestId("settings-frontend-version")).toBeInTheDocument();
  });

  it("shows red badges when subsystem booleans are false", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({
          status: "degraded",
          db: false,
          redis: false,
          worker: false,
          version: "0.9.0",
        }),
      ),
    );
    renderWithProviders(<Settings />);
    await waitFor(() =>
      expect(screen.getByTestId("settings-backend-status")).toHaveTextContent("degraded"),
    );
    expect(screen.getByTestId("settings-db-status")).toHaveTextContent("down");
    expect(screen.getByTestId("settings-redis-status")).toHaveTextContent("down");
    expect(screen.getByTestId("settings-worker-status")).toHaveTextContent("down");
  });

  it("renders dashes + error callout when /api/health/ is unreachable", async () => {
    server.use(msw.get("/api/health/", () => HttpResponse.error()));
    renderWithProviders(<Settings />);
    expect(
      await screen.findByText(/Backend unreachable/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("settings-backend-status")).toHaveTextContent("—");
    expect(screen.getByTestId("settings-db-status")).toHaveTextContent("—");
    expect(screen.getByTestId("settings-backend-version")).toHaveTextContent("—");
  });

  it("renders dashes for missing optional fields (redis/worker/version)", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({ status: "ok", db: true }),
      ),
    );
    renderWithProviders(<Settings />);
    await waitFor(() =>
      expect(screen.getByTestId("settings-backend-status")).toHaveTextContent("ok"),
    );
    expect(screen.getByTestId("settings-redis-status")).toHaveTextContent("—");
    expect(screen.getByTestId("settings-worker-status")).toHaveTextContent("—");
    expect(screen.getByTestId("settings-backend-version")).toHaveTextContent("—");
  });
});
