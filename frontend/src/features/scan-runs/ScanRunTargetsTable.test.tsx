import { describe, it, expect } from "vitest";
import { screen, within } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import { ScanRunTargetsTable } from "./ScanRunTargetsTable";

const handler = (rows: unknown[], over: { count?: number; next?: string | null } = {}) =>
  msw.get("/api/scan-runs/r-1/target-runs/", () =>
    HttpResponse.json({ count: over.count ?? rows.length, next: over.next ?? null, previous: null, results: rows }),
  );

describe("ScanRunTargetsTable", () => {
  it("renders rows with target_host, status badge, counts, timestamps", async () => {
    server.use(handler([
      makeScanTargetRun({
        id: "tr-1",
        target_host: "example.test",
        target_base_url: "https://example.test",
        status: "done",
        started_at: "2026-05-19T10:00:00Z",
        finished_at: "2026-05-19T10:01:23Z",
        findings_count: 2,
        evidence_count: 3,
      }),
    ]));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    const row = await screen.findByTestId("target-run-row-tr-1");
    expect(within(row).getByText("example.test")).toBeInTheDocument();
    expect(within(row).getByText("https://example.test")).toBeInTheDocument();
    expect(within(row).getByTestId("status-done")).toBeInTheDocument();
    expect(within(row).getByText("2026-05-19T10:00:00")).toBeInTheDocument();
    expect(within(row).getByText("2026-05-19T10:01:23")).toBeInTheDocument();
    expect(within(row).getByText("2")).toBeInTheDocument();
    expect(within(row).getByText("3")).toBeInTheDocument();
  });

  it("renders empty state when count is 0", async () => {
    server.use(handler([], { count: 0 }));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    expect(await screen.findByTestId("targets-empty")).toBeInTheDocument();
  });

  it("renders loading placeholder before first response", () => {
    server.use(handler([]));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    expect(screen.getByTestId("targets-loading")).toBeInTheDocument();
  });

  it.each([
    ["queued", null, null, "—", "—"],
    ["running", "2026-05-19T10:00:00Z", null, "2026-05-19T10:00:00", "—"],
    ["paused", "2026-05-19T10:00:00Z", null, "2026-05-19T10:00:00", "—"],
  ] as const)(
    "renders %s row with started_at=%s finished_at=%s → cells %s / %s",
    async (status, started_at, finished_at, startCell, finCell) => {
      server.use(handler([
        makeScanTargetRun({ id: `tr-${status}`, status, started_at, finished_at }),
      ]));
      renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
      const row = await screen.findByTestId(`target-run-row-tr-${status}`);
      const cells = within(row).getAllByRole("cell");
      expect(cells[2].textContent).toBe(startCell);
      expect(cells[3].textContent).toBe(finCell);
    },
  );

  it.each([
    ["done", "tr-done", "2026-05-19T10:00:00Z", "2026-05-19T10:00:42Z", "2026-05-19T10:00:00", "2026-05-19T10:00:42"],
    ["failed", "tr-failed", "2026-05-19T10:00:00Z", "2026-05-19T10:00:05Z", "2026-05-19T10:00:00", "2026-05-19T10:00:05"],
    ["stopped", "tr-stopped-r", "2026-05-19T10:00:00Z", "2026-05-19T10:00:30Z", "2026-05-19T10:00:00", "2026-05-19T10:00:30"],
  ] as const)(
    "renders %s row with both timestamps set",
    async (status, id, started_at, finished_at, startCell, finCell) => {
      server.use(handler([
        makeScanTargetRun({ id, status, started_at, finished_at }),
      ]));
      renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
      const row = await screen.findByTestId(`target-run-row-${id}`);
      expect(within(row).getByTestId(`status-${status}`)).toBeInTheDocument();
      const cells = within(row).getAllByRole("cell");
      expect(cells[2].textContent).toBe(startCell);
      expect(cells[3].textContent).toBe(finCell);
    },
  );

  it("renders stopped-from-queued row (null started_at, set finished_at)", async () => {
    server.use(handler([
      makeScanTargetRun({
        id: "tr-stopped-q",
        status: "stopped",
        started_at: null,
        finished_at: "2026-05-19T10:00:00Z",
      }),
    ]));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    const row = await screen.findByTestId("target-run-row-tr-stopped-q");
    const cells = within(row).getAllByRole("cell");
    expect(cells[2].textContent).toBe("—");
    expect(cells[3].textContent).toBe("2026-05-19T10:00:00");
  });

  it("renders truncation footer when next !== null", async () => {
    server.use(handler([makeScanTargetRun({ id: "tr-1" })], { count: 75, next: "?page=2" }));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    expect(await screen.findByTestId("targets-truncation")).toHaveTextContent(
      "Showing first 1 of 75 targets",
    );
  });

  it("renders inline error callout on target-runs 500 (parent already loaded)", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => new HttpResponse(null, { status: 500 })),
    );
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    expect(await screen.findByText(/Could not load target rows/)).toBeInTheDocument();
  });
});
