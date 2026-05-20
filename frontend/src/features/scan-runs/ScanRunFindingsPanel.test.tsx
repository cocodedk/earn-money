import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withPaginated } from "../../test/helpers";
import { ScanRunFindingsPanel } from "./ScanRunFindingsPanel";
import { makeFinding } from "./__fixtures__/finding";

const SCAN_RUN_ID = "11111111-1111-1111-1111-111111111111";

describe("ScanRunFindingsPanel", () => {
  it("renders heading with count", async () => {
    withPaginated("/api/findings/", [
      makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa", title: "A" }),
      makeFinding({ id: "ffffffff-bbbb-bbbb-bbbb-bbbbbbbbbbbb", title: "B" }),
      makeFinding({ id: "ffffffff-cccc-cccc-cccc-cccccccccccc", title: "C" }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByText(/Findings \(3\)/)).toBeInTheDocument();
  });

  it("renders all seven column headers in order", async () => {
    withPaginated("/api/findings/", [
      makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    await screen.findByText(/Findings \(1\)/);
    const headers = screen.getAllByRole("columnheader").map((th) => th.textContent);
    expect(headers).toEqual([
      "Title",
      "Target",
      "Category",
      "Severity",
      "Confidence",
      "Status",
      "Created at",
    ]);
  });

  it("renders one row per finding", async () => {
    withPaginated("/api/findings/", [
      makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa", title: "A" }),
      makeFinding({ id: "ffffffff-bbbb-bbbb-bbbb-bbbbbbbbbbbb", title: "B" }),
      makeFinding({ id: "ffffffff-cccc-cccc-cccc-cccccccccccc", title: "C" }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const rows = await screen.findAllByTestId(/^finding-row-/);
    expect(rows).toHaveLength(3);
  });

  it("gives each row data-testid=finding-row-{id}", async () => {
    withPaginated("/api/findings/", [
      makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(
      await screen.findByTestId("finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    ).toBeInTheDocument();
  });

  it("renders loading state with data-testid=findings-loading", async () => {
    server.use(
      msw.get("/api/findings/", () => new Promise<Response>(() => {})),
    );
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByTestId("findings-loading")).toBeInTheDocument();
  });

  it("renders Callout when query errors", async () => {
    server.use(msw.get("/api/findings/", () => HttpResponse.error()));
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByText(/Could not load findings/)).toBeInTheDocument();
  });

  it("renders empty state with data-testid=findings-empty and Findings (0)", async () => {
    withPaginated("/api/findings/", []);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByTestId("findings-empty")).toBeInTheDocument();
    expect(screen.getByText(/Findings \(0\)/)).toBeInTheDocument();
  });

  it("formats created_at to YYYY-MM-DD", async () => {
    withPaginated("/api/findings/", [
      makeFinding({
        id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        created_at: "2026-05-20T08:00:00Z",
      }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const row = await screen.findByTestId(
      "finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    );
    expect(within(row).getByText("2026-05-20")).toBeInTheDocument();
  });

  it("renders truncation footer when next !== null", async () => {
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json({
          count: 75,
          next: "/api/findings/?scan_run=x&page=2",
          previous: null,
          results: [makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa" })],
        }),
      ),
    );
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const footer = await screen.findByTestId("findings-truncation");
    expect(footer).toHaveTextContent("Showing first 1 of 75 findings");
  });

  it("does NOT render truncation footer when next === null", async () => {
    withPaginated("/api/findings/", [
      makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    await screen.findByTestId("finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    expect(screen.queryByTestId("findings-truncation")).toBeNull();
  });

  it("truncates target UUID to first 8 chars inside a <code> element", async () => {
    withPaginated("/api/findings/", [
      makeFinding({
        id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        target: "22222222-2222-2222-2222-222222222222",
      }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const row = await screen.findByTestId(
      "finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    );
    const code = within(row).getByText("22222222");
    expect(code.tagName).toBe("CODE");
  });

  it("renders severity/confidence/status as plain text", async () => {
    withPaginated("/api/findings/", [
      makeFinding({
        id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        severity: "high",
        confidence: "medium",
        status: "candidate",
      }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const row = await screen.findByTestId(
      "finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    );
    expect(within(row).getByText("high")).toBeInTheDocument();
    expect(within(row).getByText("medium")).toBeInTheDocument();
    expect(within(row).getByText("candidate")).toBeInTheDocument();
  });
});
