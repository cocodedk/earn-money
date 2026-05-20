import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import { makeEvidence } from "./features/scan-runs/__fixtures__/evidence";
import { makeScanRun } from "./features/scan-runs/__fixtures__/scan-run";
import { makeFinding } from "./features/scan-runs/__fixtures__/finding";
import App from "./App";

beforeEach(() => window.localStorage.clear());

const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 1,
  scan_run_count: 1,
  created_at: "2026-05-19T08:00:00.000000Z",
};

const TARGET = {
  id: "t-e2e",
  project: "p-1",
  base_url: "https://dvwa.cocode.dk",
  host: "dvwa.cocode.dk",
  ip: null,
  status: "active" as const,
  created_at: "2026-05-19T08:00:00Z",
  updated_at: "2026-05-19T08:00:00Z",
};

function paged<T>(rows: T[]) {
  return { count: rows.length, next: null, previous: null, results: rows };
}

describe("end-to-end · evidence", () => {
  it("lists evidence, filters by project, then drills into detail", async () => {
    const allEvidence = [
      makeEvidence({ id: "ev-1", field: "X-Frame-Options" }),
      makeEvidence({ id: "ev-2", field: "Content-Security-Policy" }),
      makeEvidence({ id: "ev-3", field: "Strict-Transport-Security" }),
    ];

    server.use(
      msw.get("/api/projects/", () => HttpResponse.json(paged([PROJECT]))),
      msw.get("/api/targets/", () => HttpResponse.json(paged([TARGET]))),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json(paged([makeScanRun({ id: "sr-1" })])),
      ),
      msw.get("/api/findings/", () =>
        HttpResponse.json(paged([makeFinding({ id: "f-1" })])),
      ),
      msw.get("/api/evidence/", ({ request }) => {
        const project = new URL(request.url).searchParams.get("project");
        const rows = project === "p-1" ? [allEvidence[0]] : allEvidence;
        return HttpResponse.json(paged(rows));
      }),
      msw.get("/api/evidence/ev-1/", () =>
        HttpResponse.json(
          makeEvidence({
            id: "ev-1",
            url: "https://dvwa.cocode.dk/login",
            source: "http-headers",
            field: "X-Frame-Options",
            matched_value: "ALLOWALL",
            raw_excerpt: "HTTP/1.1 200 OK\nX-Frame-Options: ALLOWALL",
          }),
        ),
      ),
    );

    renderWithProviders(<App />, { route: "/evidence" });

    expect(await screen.findByTestId("evidence-row-ev-1")).toBeInTheDocument();
    expect(await screen.findByTestId("evidence-row-ev-2")).toBeInTheDocument();
    expect(await screen.findByTestId("evidence-row-ev-3")).toBeInTheDocument();

    const project = await screen.findByLabelText("Project");
    await userEvent.selectOptions(project, "p-1");
    await waitFor(() =>
      expect(screen.queryByTestId("evidence-row-ev-2")).toBeNull(),
    );
    expect(screen.queryByTestId("evidence-row-ev-3")).toBeNull();
    expect(await screen.findByTestId("evidence-row-ev-1")).toBeInTheDocument();

    const row = await screen.findByTestId("evidence-row-ev-1");
    const openLink = row.querySelector('a[href="/evidence/ev-1"]');
    expect(openLink).not.toBeNull();
    await userEvent.click(openLink as HTMLElement);

    expect(
      await screen.findByRole("heading", { name: "Evidence" }),
    ).toBeInTheDocument();
    expect(screen.getByText("https://dvwa.cocode.dk/login")).toBeInTheDocument();
    expect(screen.getByText("http-headers")).toBeInTheDocument();
    expect(screen.getByText("X-Frame-Options")).toBeInTheDocument();
    expect(screen.getByText("ALLOWALL")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-raw-excerpt")).toHaveTextContent(
      "X-Frame-Options: ALLOWALL",
    );
  });
});
