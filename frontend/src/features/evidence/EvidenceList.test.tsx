import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { EvidenceList } from "./EvidenceList";
import { makeEvidence } from "../scan-runs/__fixtures__/evidence";
import { paged, setupFiltersRefData } from "./__fixtures__/refData";

describe("EvidenceList — rendering", () => {
  it("renders header, filters and a row per evidence", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json(
          paged([makeEvidence({ id: "e-1" }), makeEvidence({ id: "e-2" })]),
        ),
      ),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });

    expect(
      await screen.findByRole("heading", { name: "Evidence" }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("evidence-row-e-1")).toBeInTheDocument();
    expect(await screen.findByTestId("evidence-row-e-2")).toBeInTheDocument();
    expect(screen.getByLabelText("Project")).toBeInTheDocument();
    expect(screen.getByLabelText("Target")).toBeInTheDocument();
    expect(screen.getByLabelText("Scan run")).toBeInTheDocument();
    expect(screen.getByLabelText("Finding")).toBeInTheDocument();
    expect(screen.getByLabelText("Source")).toBeInTheDocument();
  });

  it("shows actions linking to /evidence/<id> and /findings/<finding>", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json(
          paged([makeEvidence({ id: "e-1", finding: "f-1" })]),
        ),
      ),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    const row = await screen.findByTestId("evidence-row-e-1");
    expect(row.querySelector('a[href="/evidence/e-1"]')).not.toBeNull();
    expect(
      row.querySelector('a[href="/findings/f-1"]'),
    ).not.toBeNull();
    expect(
      screen.getByTestId("evidence-finding-link-e-1"),
    ).toBeInTheDocument();
  });

  it("omits the finding link when evidence.finding is null", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json(paged([makeEvidence({ id: "e-1", finding: null })])),
      ),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    await screen.findByTestId("evidence-row-e-1");
    expect(
      screen.queryByTestId("evidence-finding-link-e-1"),
    ).toBeNull();
  });

  it("renders em-dash for blank url / method / field / matched_value", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json(
          paged([
            makeEvidence({
              id: "e-blank",
              url: null,
              method: null,
              field: null,
              matched_value: null,
            }),
          ]),
        ),
      ),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    const row = await screen.findByTestId("evidence-row-e-blank");
    // 4 nullable columns + the matched_value <code> wrapper all render —
    expect(row.textContent?.match(/—/g)?.length).toBeGreaterThanOrEqual(4);
  });

  it("renders empty state when no evidence matches", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/evidence/", () => HttpResponse.json(paged([]))),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    expect(
      await screen.findByText("No evidence matches the current filters."),
    ).toBeInTheDocument();
  });

  it("shows the truncation footer when data.next is set", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json(paged([makeEvidence({ id: "e-1" })], "?page=2")),
      ),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    expect(
      await screen.findByTestId("evidence-truncation"),
    ).toBeInTheDocument();
  });

  it("renders backend error callout", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    expect(
      await screen.findByText("Could not load evidence."),
    ).toBeInTheDocument();
  });
});
