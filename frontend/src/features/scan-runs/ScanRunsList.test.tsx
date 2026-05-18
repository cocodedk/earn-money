import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ScanRunsList } from "./ScanRunsList";

beforeEach(() => window.localStorage.clear());

function withProjectAndScanRuns(scanRuns: unknown[]) {
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
            scan_run_count: scanRuns.length,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
        ],
      }),
    ),
    msw.get("/api/scan-runs/", () =>
      HttpResponse.json({
        count: scanRuns.length,
        next: null,
        previous: null,
        results: scanRuns,
      }),
    ),
  );
}

describe("ScanRunsList", () => {
  it("shows the skeleton while loading", () => {
    withProjectAndScanRuns([]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("shows the empty state with a Create scan run action", async () => {
    withProjectAndScanRuns([]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(await screen.findByText(/no scan runs yet/i)).toBeInTheDocument();
  });

  it("renders rows with status badge + finished_at fallback", async () => {
    withProjectAndScanRuns([
      {
        id: "r1",
        project: "p1",
        stub_slug: "1.1",
        status: "running",
        target_run_count: 2,
        findings_count: 0,
        started_at: "2026-05-18T20:00:00.000000Z",
        finished_at: null,
        created_at: "2026-05-18T20:00:00.000000Z",
      },
    ]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(await screen.findByText("1.1")).toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveAttribute(
      "data-status",
      "running",
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("links each row id to /scan-runs/<id>", async () => {
    withProjectAndScanRuns([
      {
        id: "r-abc12345",
        project: "p1",
        stub_slug: "1.1",
        status: "queued",
        target_run_count: 1,
        findings_count: 0,
        started_at: null,
        finished_at: null,
        created_at: "2026-05-18T20:00:00.000000Z",
      },
    ]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    const link = await screen.findByRole("link", { name: /r-abc123/ });
    expect(link).toHaveAttribute("href", "/scan-runs/r-abc12345");
  });

  it("renders a callout with retry on fetch error", async () => {
    server.use(msw.get("/api/scan-runs/", () => HttpResponse.error()));
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });

  it("re-fetches when Retry is clicked", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/", () => {
        calls += 1;
        return HttpResponse.error();
      }),
    );
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    await screen.findByText(/backend unreachable/i);
    const first = calls;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(first));
  });

  it("has Create scan run link to /scan-runs/new in the page header", async () => {
    withProjectAndScanRuns([]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    const link = await screen.findByTestId("page-header-create");
    expect(link).toHaveAttribute("href", "/scan-runs/new");
  });

  it("navigates from the empty-state Create scan run button", async () => {
    withProjectAndScanRuns([]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    const button = await screen.findByRole("button", {
      name: "Create scan run",
    });
    await userEvent.click(button);
    expect(screen.getByTestId("page-header-create")).toBeInTheDocument();
  });

  it("renders started_at and finished_at when both present", async () => {
    withProjectAndScanRuns([
      {
        id: "r1",
        project: "p1",
        stub_slug: "1.1",
        status: "done",
        target_run_count: 1,
        findings_count: 0,
        started_at: "2026-05-18T20:00:00.000000Z",
        finished_at: "2026-05-18T20:01:00.000000Z",
        created_at: "2026-05-18T20:00:00.000000Z",
      },
    ]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(await screen.findByText("2026-05-18 20:00:00")).toBeInTheDocument();
    expect(screen.getByText("2026-05-18 20:01:00")).toBeInTheDocument();
  });
});
