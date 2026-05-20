import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withPaginated } from "../../test/helpers";
import { ScanRunEvidencePanel } from "./ScanRunEvidencePanel";
import { makeEvidence } from "./__fixtures__/evidence";

const SCAN_RUN_ID = "11111111-1111-1111-1111-111111111111";

describe("ScanRunEvidencePanel", () => {
  it("renders heading with count", async () => {
    withPaginated("/api/evidence/", [
      makeEvidence({ id: "eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
      makeEvidence({ id: "eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbbb" }),
      makeEvidence({ id: "eeeeeeee-cccc-cccc-cccc-cccccccccccc" }),
    ]);
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByText(/Evidence \(3\)/)).toBeInTheDocument();
  });

  it("renders all seven column headers in order", async () => {
    withPaginated("/api/evidence/", [makeEvidence()]);
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const headers = await screen.findAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "Source",
      "Target",
      "URL",
      "Method",
      "Field",
      "Matched value",
      "Created at",
    ]);
  });

  it("renders one row per evidence", async () => {
    withPaginated("/api/evidence/", [
      makeEvidence({ id: "eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
      makeEvidence({ id: "eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbbb" }),
      makeEvidence({ id: "eeeeeeee-cccc-cccc-cccc-cccccccccccc" }),
    ]);
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const rows = await screen.findAllByTestId(/^evidence-row-/);
    expect(rows).toHaveLength(3);
  });

  it("each row has data-testid=evidence-row-{id}", async () => {
    withPaginated("/api/evidence/", [
      makeEvidence({ id: "eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
    ]);
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(
      await screen.findByTestId("evidence-row-eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    ).toBeInTheDocument();
  });

  it("renders loading state with data-testid=evidence-loading", () => {
    server.use(
      msw.get("/api/evidence/", () => new Promise<Response>(() => {})),
    );
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(screen.getByTestId("evidence-loading")).toBeInTheDocument();
  });

  it("renders Callout when query errors", async () => {
    server.use(msw.get("/api/evidence/", () => HttpResponse.error()));
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByText(/Could not load evidence/)).toBeInTheDocument();
  });

  it("renders empty state with data-testid=evidence-empty + heading Evidence (0)", async () => {
    withPaginated("/api/evidence/", []);
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByTestId("evidence-empty")).toBeInTheDocument();
    expect(screen.getByText(/Evidence \(0\)/)).toBeInTheDocument();
  });

  it("formats created_at to YYYY-MM-DD", async () => {
    withPaginated("/api/evidence/", [
      makeEvidence({
        id: "eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        created_at: "2026-05-20T08:00:00Z",
      }),
    ]);
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const row = await screen.findByTestId("evidence-row-eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    expect(within(row).getByText("2026-05-20")).toBeInTheDocument();
  });

  it("renders truncation footer when next !== null", async () => {
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json({
          count: 75,
          next: "/api/evidence/?scan_run=11111111-1111-1111-1111-111111111111&page=2",
          previous: null,
          results: [makeEvidence({ id: "eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa" })],
        }),
      ),
    );
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByTestId("evidence-truncation")).toHaveTextContent(
      "Showing first 1 of 75 evidence",
    );
  });

  it("does NOT render truncation footer when next === null", async () => {
    withPaginated("/api/evidence/", [
      makeEvidence({ id: "eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
    ]);
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    await screen.findByTestId("evidence-row-eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    expect(screen.queryByTestId("evidence-truncation")).toBeNull();
  });

  it("renders null url/method/field/matched_value as —", async () => {
    withPaginated("/api/evidence/", [
      makeEvidence({
        id: "eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        url: null,
        method: null,
        field: null,
        matched_value: null,
      }),
    ]);
    renderWithProviders(
      <ScanRunEvidencePanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    const row = await screen.findByTestId("evidence-row-eeeeeeee-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    const cells = within(row).getAllByRole("cell");
    // Cells: [Source, Target, URL, Method, Field, Matched value, Created]
    expect(cells[2].textContent).toBe("—");
    expect(cells[3].textContent).toBe("—");
    expect(cells[4].textContent).toBe("—");
    expect(cells[5].textContent).toBe("—");
  });
});
