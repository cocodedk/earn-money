import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { TargetResult } from "./TargetResult";

function mountAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/targets/:id/results" element={<TargetResult />} />
    </Routes>,
    { route },
  );
}

const sampleTarget = {
  id: "t1",
  project: "p1",
  base_url: "https://dvwa.cocode.dk",
  host: "dvwa.cocode.dk",
  ip: "89.167.63.167",
  status: "active",
  created_at: "2026-05-18T20:00:00.000000Z",
};

function setupGoodTarget(args: {
  findings?: unknown[];
  evidence?: unknown[];
  scanRuns?: unknown[];
} = {}) {
  const { findings = [], evidence = [], scanRuns = [] } = args;
  server.use(
    msw.get("/api/targets/t1/", () => HttpResponse.json(sampleTarget)),
    msw.get("/api/findings/", () =>
      HttpResponse.json({
        count: findings.length,
        next: null,
        previous: null,
        results: findings,
      }),
    ),
    msw.get("/api/evidence/", () =>
      HttpResponse.json({
        count: evidence.length,
        next: null,
        previous: null,
        results: evidence,
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

describe("TargetResult", () => {
  it("renders the target summary header", async () => {
    setupGoodTarget();
    mountAt("/targets/t1/results");
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "https://dvwa.cocode.dk",
      }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveAttribute(
      "data-status",
      "active",
    );
  });

  it("renders sections for scan runs, findings, evidence with empty states", async () => {
    setupGoodTarget();
    mountAt("/targets/t1/results");
    await screen.findByRole("heading", {
      level: 1,
      name: "https://dvwa.cocode.dk",
    });
    expect(
      screen.getByRole("heading", { name: "Latest scan runs for target" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Findings for target" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Evidence for target" }),
    ).toBeInTheDocument();
  });

  it("populates the Findings section when present", async () => {
    setupGoodTarget({
      findings: [
        {
          id: "f1",
          scan_run: "r1",
          target: "t1",
          stub_slug: "1.1",
          title: "Express detected",
          category: "framework-detection",
          severity: "info",
          confidence: "high",
          status: "candidate",
          data: {},
          created_at: "2026-05-18T20:00:00.000000Z",
          updated_at: "2026-05-18T20:00:00.000000Z",
        },
      ],
    });
    mountAt("/targets/t1/results");
    expect(await screen.findByText("Express detected")).toBeInTheDocument();
  });

  it("renders the not-found callout on 404", async () => {
    server.use(
      msw.get("/api/targets/t9/", () =>
        HttpResponse.json({ detail: "Not found." }, { status: 404 }),
      ),
      msw.get("/api/findings/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/evidence/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    mountAt("/targets/t9/results");
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
