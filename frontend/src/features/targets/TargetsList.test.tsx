import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { TargetsList } from "./TargetsList";

beforeEach(() => window.localStorage.clear());

function withProjectsAndTargets(targets: unknown[]) {
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "p1",
            name: "Local Lab",
            description: "",
            target_count: targets.length,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
        ],
      }),
    ),
    msw.get("/api/targets/", () =>
      HttpResponse.json({
        count: targets.length,
        next: null,
        previous: null,
        results: targets,
      }),
    ),
  );
}

describe("TargetsList", () => {
  it("prompts to select a project when none is current", () => {
    withProjectsAndTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(screen.getByText(/select a project/i)).toBeInTheDocument();
  });

  it("renders rows when a current project is set", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    withProjectsAndTargets([
      {
        id: "t1",
        project: "p1",
        base_url: "https://dvwa.cocode.dk",
        host: "dvwa.cocode.dk",
        ip: "89.167.63.167",
        status: "active",
        created_at: "2026-05-18T20:00:00.000000Z",
      },
    ]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText("https://dvwa.cocode.dk")).toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveAttribute(
      "data-status",
      "active",
    );
  });

  it("shows the empty state with an Add target action", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    withProjectsAndTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText(/no targets yet/i)).toBeInTheDocument();
  });

  it("has an Add target link in the page header that goes to /targets/new", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    withProjectsAndTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    const link = await screen.findByTestId("page-header-create");
    expect(link).toHaveAttribute("href", "/targets/new");
  });

  it("renders a callout with retry on fetch error", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "p1",
              name: "Lab",
              description: "",
              target_count: 0,
              scan_run_count: 0,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
      msw.get("/api/targets/", () => HttpResponse.error()),
    );
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });

  it("re-fetches when Retry is clicked", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    let calls = 0;
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "p1",
              name: "Lab",
              description: "",
              target_count: 0,
              scan_run_count: 0,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
      msw.get("/api/targets/", () => {
        calls += 1;
        return HttpResponse.error();
      }),
    );
    renderWithProviders(<TargetsList />, { route: "/targets" });
    await screen.findByText(/backend unreachable/i);
    const first = calls;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(first));
  });

  it("falls back to dashes when host and ip are null", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    withProjectsAndTargets([
      {
        id: "t1",
        project: "p1",
        base_url: "https://dvwa.cocode.dk",
        host: null,
        ip: null,
        status: "active",
        created_at: "2026-05-18T20:00:00.000000Z",
      },
    ]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    await screen.findByText("https://dvwa.cocode.dk");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("navigates from the empty-state Add target button", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    withProjectsAndTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    const button = await screen.findByRole("button", { name: "Add target" });
    await userEvent.click(button);
    expect(screen.getByTestId("page-header-create")).toBeInTheDocument();
  });
});
