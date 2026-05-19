import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { EvidenceDetail } from "./EvidenceDetail";

function mountAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/evidence/:id" element={<EvidenceDetail />} />
    </Routes>,
    { route },
  );
}

const sampleEvidence = {
  id: "e1",
  scan_run: "r1",
  target: "t1",
  finding: "f1",
  source: "header.X-Powered-By",
  url: "https://dvwa.cocode.dk/",
  method: "GET",
  field: "X-Powered-By",
  matched_value: "PHP/7.4",
  raw_excerpt: "X-Powered-By: PHP/7.4",
  content_hash: "ab12cd34",
  data: { extra: "x" },
  created_at: "2026-05-18T20:00:00.000000Z",
};

describe("EvidenceDetail", () => {
  it("renders all spec fields with finding link", async () => {
    server.use(
      msw.get("/api/evidence/e1/", () => HttpResponse.json(sampleEvidence)),
    );
    mountAt("/evidence/e1");
    expect(await screen.findByText("PHP/7.4")).toBeInTheDocument();
    expect(screen.getByText("header.X-Powered-By")).toBeInTheDocument();
    expect(screen.getByText("ab12cd34")).toBeInTheDocument();
    expect(screen.getByText(/"extra": "x"/)).toBeInTheDocument();
    const findingLink = screen.getByRole("link", { name: "f1" });
    expect(findingLink).toHaveAttribute("href", "/findings/f1");
  });

  it("renders 'unlinked' when finding is null", async () => {
    server.use(
      msw.get("/api/evidence/e2/", () =>
        HttpResponse.json({ ...sampleEvidence, id: "e2", finding: null }),
      ),
    );
    mountAt("/evidence/e2");
    expect(await screen.findByText(/unlinked/i)).toBeInTheDocument();
  });

  it("falls back to dashes for nullable fields", async () => {
    server.use(
      msw.get("/api/evidence/e3/", () =>
        HttpResponse.json({
          ...sampleEvidence,
          id: "e3",
          url: null,
          method: null,
          field: null,
          matched_value: null,
          raw_excerpt: null,
          finding: null,
        }),
      ),
    );
    mountAt("/evidence/e3");
    await screen.findByText("header.X-Powered-By");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
  });

  it("renders not-found callout on 404", async () => {
    server.use(
      msw.get("/api/evidence/e9/", () =>
        HttpResponse.json({ detail: "Not found." }, { status: 404 }),
      ),
    );
    mountAt("/evidence/e9");
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
