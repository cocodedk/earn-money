import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import App from "./App";

type StoredProject = { name: string; description: string } | null;

beforeEach(() => window.localStorage.clear());

describe("end-to-end slice 1", () => {
  it("creates a project and lands on a populated list", async () => {
    let stored: StoredProject = null;
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: stored ? 1 : 0,
          next: null,
          previous: null,
          results: stored
            ? [
                {
                  id: "u-1",
                  ...stored,
                  target_count: 0,
                  scan_run_count: 0,
                  created_at: "2026-05-18T20:00:00.000000Z",
                },
              ]
            : [],
        }),
      ),
      msw.post("/api/projects/", async ({ request }) => {
        stored = (await request.json()) as StoredProject;
        return HttpResponse.json(
          {
            id: "u-1",
            ...stored,
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<App />, { route: "/projects" });

    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("page-header-create"));
    await userEvent.type(screen.getByLabelText(/Name/), "Local Lab");
    await userEvent.type(screen.getByLabelText(/Description/), "lab");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));

    await waitFor(() => {
      expect(screen.getByText("Local Lab")).toBeInTheDocument();
    });
  });
});
