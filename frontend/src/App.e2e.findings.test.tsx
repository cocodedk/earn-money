import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import { makeFinding } from "./features/scan-runs/__fixtures__/finding";
import { makeScanRun } from "./features/scan-runs/__fixtures__/scan-run";
import { makeEvidence } from "./features/scan-runs/__fixtures__/evidence";
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

const STUB = {
  slug: "1.1-headers",
  phase: 1,
  spec: 1,
  phase_slug: "p1",
  spec_slug: "headers",
  title: "Headers",
  phase_title: "Phase 1",
  category: "headers",
  status: "done" as const,
  fixture: "dvwa",
  path: "x",
};

function paged<T>(rows: T[]) {
  return { count: rows.length, next: null, previous: null, results: rows };
}

describe("end-to-end · findings", () => {
  it("lists findings, filters by project, then drills into detail", async () => {
    const allFindings = [
      makeFinding({ id: "f-1", title: "Missing CSP" }),
      makeFinding({ id: "f-2", title: "Mixed content" }),
      makeFinding({ id: "f-3", title: "X-Frame-Options" }),
    ];

    server.use(
      msw.get("/api/projects/", () => HttpResponse.json(paged([PROJECT]))),
      msw.get("/api/targets/", () => HttpResponse.json(paged([TARGET]))),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json(paged([makeScanRun({ id: "sr-1" })])),
      ),
      msw.get("/api/stubs/", () => HttpResponse.json([STUB])),
      msw.get("/api/findings/", ({ request }) => {
        const project = new URL(request.url).searchParams.get("project");
        const rows = project === "p-1" ? [allFindings[0]] : allFindings;
        return HttpResponse.json(paged(rows));
      }),
      msw.get("/api/findings/f-1/", () =>
        HttpResponse.json(makeFinding({ id: "f-1", title: "Missing CSP" })),
      ),
      msw.get("/api/evidence/", () =>
        HttpResponse.json(paged([makeEvidence({ id: "ev-1", finding: "f-1" })])),
      ),
    );

    renderWithProviders(<App />, { route: "/findings" });

    expect(await screen.findByTestId("finding-row-f-1")).toBeInTheDocument();
    expect(await screen.findByTestId("finding-row-f-2")).toBeInTheDocument();
    expect(await screen.findByTestId("finding-row-f-3")).toBeInTheDocument();

    const project = await screen.findByLabelText("Project");
    await userEvent.selectOptions(project, "p-1");
    await waitFor(() =>
      expect(screen.queryByTestId("finding-row-f-2")).toBeNull(),
    );
    expect(screen.queryByTestId("finding-row-f-3")).toBeNull();
    expect(await screen.findByTestId("finding-row-f-1")).toBeInTheDocument();

    const row = await screen.findByTestId("finding-row-f-1");
    const openLink = row.querySelector('a[href="/findings/f-1"]');
    expect(openLink).not.toBeNull();
    await userEvent.click(openLink as HTMLElement);

    expect(
      await screen.findByRole("heading", { name: /Missing CSP/ }),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("finding-evidence-row-ev-1"),
    ).toBeInTheDocument();
  });
});
