import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { FindingDetail } from "./FindingDetail";

function mountAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/findings/:id" element={<FindingDetail />} />
    </Routes>,
    { route },
  );
}

const sampleFinding = {
  id: "f1",
  scan_run: "r1",
  target: "t1",
  stub_slug: "1.1",
  title: "Express detected",
  category: "framework-detection",
  severity: "info",
  confidence: "high",
  status: "candidate",
  data: { technology: "Express", version: "4.x" },
  created_at: "2026-05-18T20:00:00.000000Z",
  updated_at: "2026-05-18T20:00:00.000000Z",
};

describe("FindingDetail", () => {
  it("renders the finding fields with severity badge", async () => {
    server.use(
      msw.get("/api/findings/f1/", () => HttpResponse.json(sampleFinding)),
      msw.get("/api/evidence/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    mountAt("/findings/f1");
    expect(await screen.findByText("Express detected")).toBeInTheDocument();
    expect(screen.getByText("framework-detection")).toBeInTheDocument();
    expect(screen.getByTestId("severity-badge")).toHaveAttribute(
      "data-severity",
      "info",
    );
    expect(screen.getByText(/"technology": "Express"/)).toBeInTheDocument();
  });

  it("renders the linked evidence table", async () => {
    server.use(
      msw.get("/api/findings/f1/", () => HttpResponse.json(sampleFinding)),
      msw.get("/api/evidence/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "e1",
              scan_run: "r1",
              target: "t1",
              finding: "f1",
              source: "body.html",
              url: "https://x/",
              method: "GET",
              field: "<app-root>",
              matched_value: "<app-root></app-root>",
              raw_excerpt: null,
              content_hash: "ab",
              data: {},
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    mountAt("/findings/f1");
    expect(await screen.findByText("body.html")).toBeInTheDocument();
  });

  it("renders 'No linked evidence' when none", async () => {
    server.use(
      msw.get("/api/findings/f1/", () => HttpResponse.json(sampleFinding)),
      msw.get("/api/evidence/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    mountAt("/findings/f1");
    expect(
      await screen.findByText(/no linked evidence/i),
    ).toBeInTheDocument();
  });

  it("renders the not-found callout on 404", async () => {
    server.use(
      msw.get("/api/findings/f9/", () =>
        HttpResponse.json({ detail: "Not found." }, { status: 404 }),
      ),
      msw.get("/api/evidence/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    mountAt("/findings/f9");
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });

  it("falls back to dashes in the linked evidence table when fields are null", async () => {
    server.use(
      msw.get("/api/findings/f1/", () => HttpResponse.json(sampleFinding)),
      msw.get("/api/evidence/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "e1",
              scan_run: "r1",
              target: "t1",
              finding: "f1",
              source: "body.html",
              url: null,
              method: null,
              field: null,
              matched_value: null,
              raw_excerpt: null,
              content_hash: "ab",
              data: {},
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    mountAt("/findings/f1");
    await screen.findByText("body.html");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });
});
