import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { CurrentProjectChip } from "./CurrentProjectChip";

beforeEach(() => window.localStorage.clear());

function withOneProject() {
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
}

describe("CurrentProjectChip", () => {
  it("renders the no-selection state when localStorage is empty", () => {
    withOneProject();
    renderWithProviders(<CurrentProjectChip />, { route: "/" });
    expect(screen.getByText(/no project selected/i)).toBeInTheDocument();
  });

  it("renders the resolved project name", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "u-1");
    withOneProject();
    renderWithProviders(<CurrentProjectChip />, { route: "/" });
    await waitFor(() =>
      expect(screen.getByTestId("current-project-chip")).toHaveTextContent(
        "Local Lab",
      ),
    );
  });

  it("has a switch link to /projects", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "u-1");
    withOneProject();
    renderWithProviders(<CurrentProjectChip />, { route: "/" });
    const link = await screen.findByTestId("current-project-switch");
    expect(link).toHaveAttribute("href", "/projects");
    await userEvent.click(link);
  });
});
