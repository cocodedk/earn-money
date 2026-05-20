import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import App from "./App";

describe("end-to-end · settings", () => {
  it("navigates from the sidebar to /settings and renders all 6 status rows", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({
          status: "ok",
          db: true,
          redis: true,
          worker: true,
          version: "2.6.0",
        }),
      ),
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );

    renderWithProviders(<App />, { route: "/" });

    const settingsLink = await screen.findByRole("link", { name: "Settings" });
    await userEvent.click(settingsLink);

    await waitFor(() =>
      expect(screen.getByTestId("settings-backend-status")).toHaveTextContent("ok"),
    );
    expect(screen.getByTestId("settings-db-status")).toHaveTextContent("up");
    expect(screen.getByTestId("settings-redis-status")).toHaveTextContent("up");
    expect(screen.getByTestId("settings-worker-status")).toHaveTextContent("up");
    expect(screen.getByTestId("settings-backend-version")).toHaveTextContent("2.6.0");
    expect(screen.getByTestId("settings-frontend-version")).toBeInTheDocument();
  });
});
