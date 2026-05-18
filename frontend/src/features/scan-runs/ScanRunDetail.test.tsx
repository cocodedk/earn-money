import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ScanRunDetail } from "./ScanRunDetail";

function mountAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
    </Routes>,
    { route },
  );
}

function withScanRun() {
  server.use(
    msw.get("/api/scan-runs/r1/", () =>
      HttpResponse.json({
        id: "r1",
        project: "p1",
        stub_slug: "1.1",
        status: "running",
        target_run_count: 1,
        findings_count: 0,
        started_at: "2026-05-18T20:00:00.000000Z",
        finished_at: null,
        created_at: "2026-05-18T20:00:00.000000Z",
      }),
    ),
    msw.get("/api/scan-runs/r1/target-runs/", () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "tr1",
            scan_run: "r1",
            target: "t1",
            target_base_url: "https://dvwa.cocode.dk",
            status: "running",
            findings_count: 0,
            evidence_count: 0,
            started_at: "2026-05-18T20:01:00.000000Z",
            finished_at: null,
          },
        ],
      }),
    ),
    msw.get("/api/scan-runs/r1/findings/", () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
    msw.get("/api/scan-runs/r1/evidence/", () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  );
}

describe("ScanRunDetail", () => {
  it("renders header + lifecycle controls + sections", async () => {
    withScanRun();
    mountAt("/scan-runs/r1");
    expect(await screen.findByTestId("scan-run-header")).toBeInTheDocument();
    expect(screen.getByTestId("lifecycle-controls")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Targets" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Live events" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Findings" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Evidence" }),
    ).toBeInTheDocument();
  });

  it("renders the target rows", async () => {
    withScanRun();
    mountAt("/scan-runs/r1");
    expect(
      await screen.findByText("https://dvwa.cocode.dk"),
    ).toBeInTheDocument();
  });

  it("renders an error callout when the scan run cannot be loaded", async () => {
    server.use(
      msw.get("/api/scan-runs/r9/", () =>
        HttpResponse.json({ detail: "Not found." }, { status: 404 }),
      ),
      msw.get("/api/scan-runs/r9/target-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/r9/findings/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/r9/evidence/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    mountAt("/scan-runs/r9");
    await waitFor(() =>
      expect(screen.getByText(/not found/i)).toBeInTheDocument(),
    );
  });
});
