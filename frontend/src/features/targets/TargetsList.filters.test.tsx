import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { withPaginated } from "../../test/helpers";
import { renderWithProviders } from "../../test/renderWithProviders";
import { TargetsList } from "./TargetsList";

const PROJECT_A = {
  id: "p-a",
  name: "Project A",
  description: "",
  target_count: 0,
  scan_run_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
};
const PROJECT_B = {
  id: "p-b",
  name: "Project B",
  description: "",
  target_count: 0,
  scan_run_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
};

const TARGETS = [
  {
    id: "t-1",
    project: "p-a",
    base_url: "https://a-active.example",
    host: "a-active.example",
    ip: null,
    status: "active" as const,
    created_at: "2026-05-19T08:00:00.000000Z",
    updated_at: "2026-05-19T08:00:00.000000Z",
  },
  {
    id: "t-2",
    project: "p-a",
    base_url: "https://a-retired.example",
    host: "a-retired.example",
    ip: null,
    status: "retired" as const,
    created_at: "2026-05-19T08:00:00.000000Z",
    updated_at: "2026-05-19T08:00:00.000000Z",
  },
  {
    id: "t-3",
    project: "p-b",
    base_url: "https://b-active.example",
    host: "b-active.example",
    ip: null,
    status: "active" as const,
    created_at: "2026-05-19T08:00:00.000000Z",
    updated_at: "2026-05-19T08:00:00.000000Z",
  },
];

function withTargetsAndProjects() {
  withPaginated("/api/projects/", [PROJECT_A, PROJECT_B]);
  withPaginated("/api/targets/", TARGETS);
}

describe("TargetsList filters", () => {
  it("renders the filter bar with project and status selects", async () => {
    withTargetsAndProjects();
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(
      await screen.findByTestId("targets-filters-bar"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("filter-project")).toBeInTheDocument();
    expect(screen.getByTestId("filter-status")).toBeInTheDocument();
  });

  it("filters by project via URL search param", async () => {
    withTargetsAndProjects();
    renderWithProviders(<TargetsList />, { route: "/targets?project=p-b" });
    expect(
      await screen.findByText("https://b-active.example"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("https://a-active.example"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("https://a-retired.example"),
    ).not.toBeInTheDocument();
  });

  it("filters by status via URL search param", async () => {
    withTargetsAndProjects();
    renderWithProviders(<TargetsList />, { route: "/targets?status=retired" });
    expect(
      await screen.findByText("https://a-retired.example"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("https://a-active.example"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("https://b-active.example"),
    ).not.toBeInTheDocument();
  });

  it("AND-combines project and status filters", async () => {
    withTargetsAndProjects();
    renderWithProviders(<TargetsList />, {
      route: "/targets?project=p-a&status=active",
    });
    expect(
      await screen.findByText("https://a-active.example"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("https://a-retired.example"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("https://b-active.example"),
    ).not.toBeInTheDocument();
  });

  it("shows empty-state-with-filters when no targets match", async () => {
    withTargetsAndProjects();
    renderWithProviders(<TargetsList />, {
      route: "/targets?project=p-b&status=retired",
    });
    expect(
      await screen.findByText(/No targets match the current filters/i),
    ).toBeInTheDocument();
  });

  it("selecting a filter updates URL search params and narrows rows", async () => {
    withTargetsAndProjects();
    renderWithProviders(<TargetsList />, { route: "/targets" });
    await screen.findByText("https://a-active.example");
    await userEvent.selectOptions(
      screen.getByTestId("filter-status"),
      "retired",
    );
    expect(
      screen.queryByText("https://a-active.example"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("https://b-active.example"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("https://a-retired.example")).toBeInTheDocument();
  });

  it("clearing a filter (back to 'All') shows all rows again", async () => {
    withTargetsAndProjects();
    renderWithProviders(<TargetsList />, { route: "/targets?status=retired" });
    await screen.findByText("https://a-retired.example");
    expect(
      screen.queryByText("https://a-active.example"),
    ).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByTestId("filter-status"), "");
    expect(
      await screen.findByText("https://a-active.example"),
    ).toBeInTheDocument();
    expect(screen.getByText("https://b-active.example")).toBeInTheDocument();
  });

  it("renders all rows when no filter params are present", async () => {
    withTargetsAndProjects();
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(
      await screen.findByText("https://a-active.example"),
    ).toBeInTheDocument();
    expect(screen.getByText("https://a-retired.example")).toBeInTheDocument();
    expect(screen.getByText("https://b-active.example")).toBeInTheDocument();
  });
});
