import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ProjectsList } from "./ProjectsList";

function withProjects(rows: unknown[]) {
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({
        count: rows.length,
        next: null,
        previous: null,
        results: rows,
      }),
    ),
  );
}

describe("ProjectsList", () => {
  it("shows the skeleton while loading", () => {
    withProjects([]);
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("shows the empty state with a create action when there are no rows", async () => {
    withProjects([]);
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create project" })).toBeInTheDocument();
  });

  it("renders rows with denormalized counts", async () => {
    withProjects([
      {
        id: "u1",
        name: "Local Lab",
        description: "lab",
        target_count: 3,
        scan_run_count: 1,
        created_at: "2026-05-18T20:00:00.000000Z",
      },
    ]);
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    expect(await screen.findByText("Local Lab")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows a callout with retry on fetch error", async () => {
    server.use(msw.get("/api/projects/", () => HttpResponse.error()));
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("re-fetches when Retry is clicked", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/projects/", () => {
        calls += 1;
        return HttpResponse.error();
      }),
    );
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    await screen.findByText(/backend unreachable/i);
    const firstCallCount = calls;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(firstCallCount));
  });

  it("navigates from the empty-state Create button", async () => {
    withProjects([]);
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    const button = await screen.findByRole("button", { name: "Create project" });
    await userEvent.click(button);
    expect(screen.getByTestId("page-header-create")).toBeInTheDocument();
  });

  it("exposes a Create project link in the page header", async () => {
    withProjects([]);
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    const link = await screen.findByTestId("page-header-create");
    expect(link).toHaveAttribute("href", "/projects/new");
    await userEvent.click(link);
  });
});
