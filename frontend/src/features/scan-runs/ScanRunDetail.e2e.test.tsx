import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import App from "../../App";

describe("/scan-runs/:id e2e", () => {
  it("renders the 6A header AND ≥1 target row from the 6B table", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/", () =>
        HttpResponse.json(makeScanRun({ id: "r-1", status: "running" })),
      ),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 2,
          next: null,
          previous: null,
          results: [
            makeScanTargetRun({ id: "tr-1", status: "queued" }),
            makeScanTargetRun({
              id: "tr-2",
              status: "done",
              finished_at: "2026-05-19T10:00:00Z",
            }),
          ],
        }),
      ),
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "p-1",
              name: "Test",
              description: "",
              target_count: 1,
              scan_run_count: 1,
              created_at: "2026-05-19T00:00:00Z",
            },
          ],
        }),
      ),
      msw.get("/api/stubs/", () =>
        HttpResponse.json([
          { slug: "1.15", title: "Public JS bundles", status: "active" },
        ]),
      ),
    );

    renderWithProviders(<App />, { route: "/scan-runs/r-1" });

    expect(await screen.findByTestId("target-run-row-tr-1")).toBeInTheDocument();
    expect(screen.getByTestId("target-run-row-tr-2")).toBeInTheDocument();
    expect(
      screen.queryByTestId("targets-truncation"),
    ).not.toBeInTheDocument();
  });

  it("renders truncation footer when next !== null", async () => {
    server.use(
      msw.get("/api/scan-runs/r-2/", () =>
        HttpResponse.json(makeScanRun({ id: "r-2", status: "done" })),
      ),
      msw.get("/api/scan-runs/r-2/target-runs/", () =>
        HttpResponse.json({
          count: 75,
          next: "?page=2",
          previous: null,
          results: [makeScanTargetRun({ id: "tr-1" })],
        }),
      ),
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        }),
      ),
      msw.get("/api/stubs/", () => HttpResponse.json([])),
    );

    renderWithProviders(<App />, { route: "/scan-runs/r-2" });

    expect(await screen.findByTestId("targets-truncation")).toHaveTextContent(
      "Showing first 1 of 75 targets",
    );
  });
});
