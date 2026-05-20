import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { FindingDetail } from "./FindingDetail";
import { makeFinding } from "../scan-runs/__fixtures__/finding";
import { makeEvidence } from "../scan-runs/__fixtures__/evidence";
import { paged } from "./__fixtures__/refData";

const FINDING_ID = "ffffffff-1111-1111-1111-111111111111";
const TARGET_ID = "22222222-2222-2222-2222-222222222222";
const SCAN_RUN_ID = "11111111-1111-1111-1111-111111111111";

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/findings/:findingId" element={<FindingDetail />} />
    </Routes>,
    { route },
  );
}

describe("FindingDetail", () => {
  it("renders title, meta links, data JSON and the linked-evidence table", async () => {
    server.use(
      msw.get(`/api/findings/${FINDING_ID}/`, () =>
        HttpResponse.json(
          makeFinding({
            id: FINDING_ID,
            target: TARGET_ID,
            scan_run: SCAN_RUN_ID,
            title: "Reflected XSS in /search",
            data: { param: "q", payload: "<svg/onload>" },
          }),
        ),
      ),
      msw.get("/api/evidence/", () =>
        HttpResponse.json(
          paged([
            makeEvidence({ id: "e-1", finding: FINDING_ID }),
            makeEvidence({ id: "e-2", finding: FINDING_ID }),
          ]),
        ),
      ),
    );

    renderAt(`/findings/${FINDING_ID}`);

    expect(
      await screen.findByRole("heading", { name: /Reflected XSS in \/search/ }),
    ).toBeInTheDocument();

    expect(
      document.querySelector(`a[href="/targets/${TARGET_ID}/results"]`),
    ).not.toBeNull();
    expect(
      document.querySelector(`a[href="/scan-runs/${SCAN_RUN_ID}"]`),
    ).not.toBeNull();
    expect(
      document.querySelector('a[href="/stubs/1.1-headers"]'),
    ).not.toBeNull();

    const pre = document.querySelector("pre");
    expect(pre?.textContent).toContain('"param": "q"');
    expect(pre?.textContent).toContain('"payload": "<svg/onload>"');

    expect(
      await screen.findByTestId("finding-evidence-row-e-1"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("finding-evidence-row-e-2"),
    ).toBeInTheDocument();
  });

  it("requests evidence with ?finding=<id>", async () => {
    let search = "";
    server.use(
      msw.get(`/api/findings/${FINDING_ID}/`, () =>
        HttpResponse.json(makeFinding({ id: FINDING_ID })),
      ),
      msw.get("/api/evidence/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    renderAt(`/findings/${FINDING_ID}`);
    expect(await screen.findByText(/No linked evidence/)).toBeInTheDocument();
    expect(search).toBe(`?finding=${FINDING_ID}`);
  });

  it("renders 'Not found' when the finding 404s", async () => {
    server.use(
      msw.get(`/api/findings/${FINDING_ID}/`, () =>
        HttpResponse.json({ detail: "not found" }, { status: 404 }),
      ),
      msw.get("/api/evidence/", () => HttpResponse.json(paged([]))),
    );
    renderAt(`/findings/${FINDING_ID}`);
    expect(await screen.findByText("Finding not found")).toBeInTheDocument();
  });

  it("renders 'No linked evidence' empty state", async () => {
    server.use(
      msw.get(`/api/findings/${FINDING_ID}/`, () =>
        HttpResponse.json(makeFinding({ id: FINDING_ID })),
      ),
      msw.get("/api/evidence/", () => HttpResponse.json(paged([]))),
    );
    renderAt(`/findings/${FINDING_ID}`);
    expect(
      await screen.findByText("No linked evidence."),
    ).toBeInTheDocument();
  });

  it("renders em-dash when confidence is blank (contract drift)", async () => {
    server.use(
      msw.get(`/api/findings/${FINDING_ID}/`, () =>
        HttpResponse.json(
          makeFinding({
            id: FINDING_ID,
            confidence: "" as unknown as "low",
          }),
        ),
      ),
      msw.get("/api/evidence/", () => HttpResponse.json(paged([]))),
    );
    renderAt(`/findings/${FINDING_ID}`);
    const row = await screen.findByText("Confidence");
    expect(row.parentElement?.textContent).toContain("—");
  });

  it("renders error when finding load fails (non-404)", async () => {
    server.use(
      msw.get(`/api/findings/${FINDING_ID}/`, () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
      msw.get("/api/evidence/", () => HttpResponse.json(paged([]))),
    );
    renderAt(`/findings/${FINDING_ID}`);
    expect(
      await screen.findByText("Could not load finding."),
    ).toBeInTheDocument();
  });
});
