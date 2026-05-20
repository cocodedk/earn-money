import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { FindingsList } from "./FindingsList";
import { makeFinding } from "../scan-runs/__fixtures__/finding";
import { paged, setupFiltersRefData } from "./__fixtures__/refData";

describe("FindingsList — rendering", () => {
  it("renders header, filters and a row per finding", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json(
          paged([makeFinding({ id: "f-1" }), makeFinding({ id: "f-2" })]),
        ),
      ),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });

    expect(
      await screen.findByRole("heading", { name: "Findings" }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("finding-row-f-1")).toBeInTheDocument();
    expect(await screen.findByTestId("finding-row-f-2")).toBeInTheDocument();
    expect(screen.getByLabelText("Project")).toBeInTheDocument();
    expect(screen.getByLabelText("Severity")).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeInTheDocument();
  });

  it("shows actions linking to /findings/<id> and /evidence?finding=<id>", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json(paged([makeFinding({ id: "f-1" })])),
      ),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    const row = await screen.findByTestId("finding-row-f-1");
    expect(row.querySelector('a[href="/findings/f-1"]')).not.toBeNull();
    expect(
      row.querySelector('a[href="/evidence?finding=f-1"]'),
    ).not.toBeNull();
  });

  it("renders empty state when no findings match", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/findings/", () => HttpResponse.json(paged([]))),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    expect(
      await screen.findByText("No findings match the current filters."),
    ).toBeInTheDocument();
  });

  it("shows the truncation footer when data.next is set", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json(paged([makeFinding({ id: "f-1" })], "?page=2")),
      ),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    expect(
      await screen.findByTestId("findings-truncation"),
    ).toBeInTheDocument();
  });

  it("renders an em-dash when confidence is blank (contract drift)", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json(
          paged([
            makeFinding({
              id: "f-blank",
              confidence: "" as unknown as "low",
            }),
          ]),
        ),
      ),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    const row = await screen.findByTestId("finding-row-f-blank");
    expect(row.textContent).toContain("—");
  });

  it("renders backend error callout", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    expect(
      await screen.findByText("Could not load findings."),
    ).toBeInTheDocument();
  });
});
