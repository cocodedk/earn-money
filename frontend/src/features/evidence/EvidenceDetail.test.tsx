import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { EvidenceDetail } from "./EvidenceDetail";
import { makeEvidence } from "../scan-runs/__fixtures__/evidence";

const EVIDENCE_ID = "eeeeeeee-1111-1111-1111-111111111111";
const TARGET_ID = "22222222-2222-2222-2222-222222222222";
const SCAN_RUN_ID = "11111111-1111-1111-1111-111111111111";
const FINDING_ID = "ffffffff-1111-1111-1111-111111111111";

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/evidence/:evidenceId" element={<EvidenceDetail />} />
    </Routes>,
    { route },
  );
}

describe("EvidenceDetail", () => {
  it("renders header, meta links, raw_excerpt and data JSON", async () => {
    server.use(
      msw.get(`/api/evidence/${EVIDENCE_ID}/`, () =>
        HttpResponse.json(
          makeEvidence({
            id: EVIDENCE_ID,
            target: TARGET_ID,
            scan_run: SCAN_RUN_ID,
            finding: FINDING_ID,
            source: "http-headers",
            url: "https://target.cocode.dk/",
            method: "GET",
            field: "X-Frame-Options",
            matched_value: "ALLOWALL",
            raw_excerpt: "HTTP/1.1 200 OK\nX-Frame-Options: ALLOWALL",
            content_hash: "deadbeef",
            data: { header: "X-Frame-Options" },
          }),
        ),
      ),
    );

    renderAt(`/evidence/${EVIDENCE_ID}`);

    expect(
      await screen.findByRole("heading", { name: "Evidence" }),
    ).toBeInTheDocument();

    expect(
      document.querySelector(`a[href="/targets/${TARGET_ID}/results"]`),
    ).not.toBeNull();
    expect(
      document.querySelector(`a[href="/scan-runs/${SCAN_RUN_ID}"]`),
    ).not.toBeNull();
    expect(
      document.querySelector(`a[href="/findings/${FINDING_ID}"]`),
    ).not.toBeNull();
    expect(
      screen.getByTestId("evidence-detail-finding-link"),
    ).toBeInTheDocument();

    const excerpt = await screen.findByTestId("evidence-raw-excerpt");
    expect(excerpt.textContent).toContain("HTTP/1.1 200 OK");
    expect(excerpt.textContent).toContain("X-Frame-Options: ALLOWALL");

    const dataPre = screen.getByTestId("evidence-data-json");
    expect(dataPre.textContent).toContain('"header": "X-Frame-Options"');
  });

  it("renders em-dash and no finding link when finding is null", async () => {
    server.use(
      msw.get(`/api/evidence/${EVIDENCE_ID}/`, () =>
        HttpResponse.json(
          makeEvidence({
            id: EVIDENCE_ID,
            finding: null,
            url: null,
            method: null,
            field: null,
            matched_value: null,
            raw_excerpt: null,
          }),
        ),
      ),
    );
    renderAt(`/evidence/${EVIDENCE_ID}`);
    await screen.findByRole("heading", { name: "Evidence" });

    expect(
      screen.queryByTestId("evidence-detail-finding-link"),
    ).toBeNull();
    const excerpt = screen.getByTestId("evidence-raw-excerpt");
    expect(excerpt.textContent).toBe("—");
    const findingRow = screen.getByText("Finding");
    expect(findingRow.parentElement?.textContent).toContain("—");
  });

  it("renders 'Not found' when the evidence 404s", async () => {
    server.use(
      msw.get(`/api/evidence/${EVIDENCE_ID}/`, () =>
        HttpResponse.json({ detail: "not found" }, { status: 404 }),
      ),
    );
    renderAt(`/evidence/${EVIDENCE_ID}`);
    expect(
      await screen.findByText("Evidence not found"),
    ).toBeInTheDocument();
  });

  it("renders error when evidence load fails (non-404)", async () => {
    server.use(
      msw.get(`/api/evidence/${EVIDENCE_ID}/`, () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    renderAt(`/evidence/${EVIDENCE_ID}`);
    expect(
      await screen.findByText("Could not load evidence."),
    ).toBeInTheDocument();
  });
});
