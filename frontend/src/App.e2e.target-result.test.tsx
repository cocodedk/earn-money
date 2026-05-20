import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import { makeScanRun } from "./features/scan-runs/__fixtures__/scan-run";
import { makeFinding } from "./features/scan-runs/__fixtures__/finding";
import { makeEvidence } from "./features/scan-runs/__fixtures__/evidence";
import { makeEvent } from "./features/scan-runs/__fixtures__/event";
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

const TARGET_ID = "t-e2e-aaaa-bbbb-cccc-dddddddddddd";

const TARGET = {
  id: TARGET_ID,
  project: "p-1",
  base_url: "https://dvwa.cocode.dk",
  host: "dvwa.cocode.dk",
  ip: "1.2.3.4",
  status: "active" as const,
  created_at: "2026-05-19T08:00:00.000000Z",
  updated_at: "2026-05-19T08:00:00.000000Z",
};

function paged<T>(rows: T[]) {
  return { count: rows.length, next: null, previous: null, results: rows };
}

describe("end-to-end · target result", () => {
  it("navigates from /targets to /targets/:id/results and renders all 5 sections", async () => {
    const scanRuns = [makeScanRun({ id: "r-e2e-target" })];
    const findings = [
      makeFinding({ id: "f-1", target: TARGET_ID }),
      makeFinding({ id: "f-2", target: TARGET_ID }),
    ];
    const evidence = [
      makeEvidence({ id: "e-1", target: TARGET_ID }),
      makeEvidence({ id: "e-2", target: TARGET_ID }),
      makeEvidence({ id: "e-3", target: TARGET_ID }),
    ];
    const events = [
      makeEvent({ id: "v-1", target: TARGET_ID }),
      makeEvent({ id: "v-2", target: TARGET_ID }),
      makeEvent({ id: "v-3", target: TARGET_ID }),
      makeEvent({ id: "v-4", target: TARGET_ID }),
    ];

    server.use(
      msw.get("/api/projects/", () => HttpResponse.json(paged([PROJECT]))),
      msw.get("/api/targets/", () => HttpResponse.json(paged([TARGET]))),
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(TARGET)),
      msw.get("/api/scan-runs/", () => HttpResponse.json(paged(scanRuns))),
      msw.get("/api/findings/", () => HttpResponse.json(paged(findings))),
      msw.get("/api/evidence/", () => HttpResponse.json(paged(evidence))),
      msw.get("/api/events/", () => HttpResponse.json(paged(events))),
    );

    renderWithProviders(<App />, { route: "/targets" });

    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      await screen.findByRole("link", { name: "Open results" }),
    );

    expect(
      await screen.findByText(
        /Target · t-e2e-aa · https:\/\/dvwa\.cocode\.dk/,
      ),
    ).toBeInTheDocument();
    expect(await screen.findByText("Local Lab")).toBeInTheDocument();
    expect(
      await screen.findByTestId("target-scan-runs-section"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("target-findings-section"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("target-evidence-section"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("target-events-section"),
    ).toBeInTheDocument();
    expect(await screen.findAllByTestId(/^target-finding-row-/)).toHaveLength(
      2,
    );
    expect(await screen.findAllByTestId(/^target-evidence-row-/)).toHaveLength(
      3,
    );
    expect(await screen.findAllByTestId(/^target-event-row-/)).toHaveLength(4);
  });
});
