import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { LocationProbe, withPaginated } from "../../test/helpers";
import { TargetsList } from "./TargetsList";

const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 1,
  scan_run_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
};

const TARGET = {
  id: "t-1",
  project: "p-1",
  base_url: "https://dvwa.cocode.dk",
  host: "dvwa.cocode.dk",
  ip: null,
  status: "active" as const,
  created_at: "2026-05-19T08:00:00.000000Z",
  updated_at: "2026-05-19T08:00:00.000000Z",
};

const withProjects = (rows: unknown[]) =>
  withPaginated("/api/projects/", rows);
const withTargets = (rows: unknown[]) => withPaginated("/api/targets/", rows);

describe("TargetsList", () => {
  it("shows a skeleton while the list is loading", () => {
    withProjects([PROJECT]);
    withTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("shows the empty state with a Create target action that navigates to /targets/new", async () => {
    withProjects([PROJECT]);
    withTargets([]);
    renderWithProviders(
      <>
        <TargetsList />
        <LocationProbe />
      </>,
      { route: "/targets" },
    );
    expect(await screen.findByText("No targets yet.")).toBeInTheDocument();
    const emptyStateCta = screen.getByRole("button", { name: "Create target" });
    expect(emptyStateCta).toBeInTheDocument();
    await userEvent.click(emptyStateCta);
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/targets/new"),
    );
  });

  it("renders rows with the project name resolved from the cached projects query", async () => {
    withProjects([PROJECT]);
    withTargets([TARGET]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(
      await screen.findByText("https://dvwa.cocode.dk"),
    ).toBeInTheDocument();
    expect(screen.getByText("dvwa.cocode.dk")).toBeInTheDocument();
    expect(screen.getByText("Local Lab")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("renders an Open results link to /targets/:id/results for each row", async () => {
    withProjects([PROJECT]);
    withTargets([TARGET]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(
      await screen.findByRole("link", { name: "Open results" }),
    ).toHaveAttribute("href", "/targets/t-1/results");
  });

  it("renders a retired status badge with the muted palette", async () => {
    withProjects([PROJECT]);
    withTargets([{ ...TARGET, status: "retired" }]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    const badge = await screen.findByTestId("status-retired");
    expect(badge.textContent).toBe("retired");
    expect(badge.className).toMatch(/bg-gray-200/);
  });

  it("falls back to the short UUID when the target's project isn't in the cached list", async () => {
    withProjects([PROJECT]);
    withTargets([{ ...TARGET, project: "p-stale-aaaa-bbbb-cccc-dddd" }]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText("p-stale-")).toBeInTheDocument();
  });

  it("shows a Backend-unreachable callout with Retry on fetch error", async () => {
    withProjects([PROJECT]);
    server.use(msw.get("/api/targets/", () => HttpResponse.error()));
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(
      await screen.findByText(/backend unreachable/i),
    ).toBeInTheDocument();
    let calls = 0;
    server.use(
      msw.get("/api/targets/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(0));
  });
});
