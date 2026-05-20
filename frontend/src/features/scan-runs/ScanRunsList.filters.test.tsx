import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { withBareArray, withPaginated } from "../../test/helpers";
import { renderWithProviders } from "../../test/renderWithProviders";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import { ScanRunsList } from "./ScanRunsList";

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

const RUNS = [
  makeScanRun({
    id: "r-a-queued-11",
    project: "p-a",
    stub_slug: "1.1",
    status: "queued",
  }),
  makeScanRun({
    id: "r-a-done-12",
    project: "p-a",
    stub_slug: "1.2",
    status: "done",
  }),
  makeScanRun({
    id: "r-b-running-11",
    project: "p-b",
    stub_slug: "1.1",
    status: "running",
  }),
];

function withDeps() {
  withPaginated("/api/projects/", [PROJECT_A, PROJECT_B]);
  withBareArray("/api/stubs/", [makeStub({ slug: "1.1" }), makeStub({ slug: "1.2" })]);
  withPaginated("/api/scan-runs/", RUNS);
}

describe("ScanRunsList filters", () => {
  it("renders the filter bar with project, stub, and status selects", async () => {
    withDeps();
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(
      await screen.findByTestId("scan-runs-filters-bar"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("filter-project")).toBeInTheDocument();
    expect(screen.getByTestId("filter-stub")).toBeInTheDocument();
    expect(screen.getByTestId("filter-status")).toBeInTheDocument();
  });

  it("filters by project via URL search param", async () => {
    withDeps();
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs?project=p-b" });
    expect(await screen.findByText("r-b-runn")).toBeInTheDocument();
    expect(screen.queryByText("r-a-queu")).not.toBeInTheDocument();
    expect(screen.queryByText("r-a-done")).not.toBeInTheDocument();
  });

  it("filters by stub via URL search param", async () => {
    withDeps();
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs?stub=1.2" });
    expect(await screen.findByText("r-a-done")).toBeInTheDocument();
    expect(screen.queryByText("r-a-queu")).not.toBeInTheDocument();
    expect(screen.queryByText("r-b-runn")).not.toBeInTheDocument();
  });

  it("filters by status via URL search param", async () => {
    withDeps();
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs?status=running" });
    expect(await screen.findByText("r-b-runn")).toBeInTheDocument();
    expect(screen.queryByText("r-a-queu")).not.toBeInTheDocument();
    expect(screen.queryByText("r-a-done")).not.toBeInTheDocument();
  });

  it("AND-combines project and status filters", async () => {
    withDeps();
    renderWithProviders(<ScanRunsList />, {
      route: "/scan-runs?project=p-a&status=done",
    });
    expect(await screen.findByText("r-a-done")).toBeInTheDocument();
    expect(screen.queryByText("r-a-queu")).not.toBeInTheDocument();
    expect(screen.queryByText("r-b-runn")).not.toBeInTheDocument();
  });

  it("shows empty-state-with-filters when no runs match", async () => {
    withDeps();
    renderWithProviders(<ScanRunsList />, {
      route: "/scan-runs?status=failed",
    });
    expect(
      await screen.findByText(/No scan runs match the current filters/i),
    ).toBeInTheDocument();
  });

  it("selecting a filter updates URL search params and narrows rows", async () => {
    withDeps();
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    await screen.findByText("r-a-queu");
    await userEvent.selectOptions(
      screen.getByTestId("filter-status"),
      "done",
    );
    expect(screen.queryByText("r-a-queu")).not.toBeInTheDocument();
    expect(screen.queryByText("r-b-runn")).not.toBeInTheDocument();
    expect(screen.getByText("r-a-done")).toBeInTheDocument();
  });

  it("clearing a filter (back to 'All') shows all rows again", async () => {
    withDeps();
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs?status=done" });
    await screen.findByText("r-a-done");
    expect(screen.queryByText("r-a-queu")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByTestId("filter-status"), "");
    expect(await screen.findByText("r-a-queu")).toBeInTheDocument();
    expect(screen.getByText("r-b-runn")).toBeInTheDocument();
  });
});
