import { describe, it, expect, beforeEach } from "vitest";
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import { lastSseInstance } from "./test/sseMock";
import App from "./App";

type StoredTarget = {
  id: string;
  project: string;
  base_url: string;
  host: string | null;
  ip: string | null;
  status: "active" | "retired";
  created_at: string;
};

type StoredScanRun = {
  id: string;
  project: string;
  stub_slug: string;
  status:
    | "queued"
    | "running"
    | "paused"
    | "stopping"
    | "stopped"
    | "failed"
    | "done";
  target_run_count: number;
  findings_count: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

const project = {
  id: "p1",
  name: "Local Lab",
  description: "lab",
  target_count: 0,
  scan_run_count: 0,
  created_at: "2026-05-19T00:00:00.000000Z",
};

const stub = {
  slug: "1.1",
  phase: 1,
  spec: 1,
  title: "Framework detection",
  status: "done",
  fixture: "juiceshop",
  category: "information-gathering",
  phase_title: "Information gathering",
  phase_slug: "01-information-gathering",
  spec_slug: "01-framework-detection",
  path: "x",
  body: "# Framework detection\n\nDetect the running framework.",
};

beforeEach(() => window.localStorage.clear());

describe("end-to-end slice 2", () => {
  it("walks Set-as-current → Add target → Create scan run → Start", async () => {
    const targets: StoredTarget[] = [];
    const scanRuns: StoredScanRun[] = [];

    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [{ ...project, target_count: targets.length }],
        }),
      ),
      msw.get("/api/targets/", () =>
        HttpResponse.json({
          count: targets.length,
          next: null,
          previous: null,
          results: targets,
        }),
      ),
      msw.post("/api/targets/", async ({ request }) => {
        const body = (await request.json()) as {
          project: string;
          base_url: string;
          host: string | null;
          ip: string | null;
        };
        const t: StoredTarget = {
          id: `t${targets.length + 1}`,
          project: body.project,
          base_url: body.base_url,
          host: body.host ?? null,
          ip: body.ip ?? null,
          status: "active",
          created_at: "2026-05-19T00:00:00.000000Z",
        };
        targets.push(t);
        return HttpResponse.json(t, { status: 201 });
      }),
      msw.get("/api/stubs/", () => HttpResponse.json([stub])),
      msw.get("/api/stubs/1.1/", () => HttpResponse.json(stub)),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({
          count: scanRuns.length,
          next: null,
          previous: null,
          results: scanRuns,
        }),
      ),
      msw.post("/api/scan-runs/", async ({ request }) => {
        const body = (await request.json()) as {
          project: string;
          stub_slug: string;
          target_ids: string[];
        };
        const run: StoredScanRun = {
          id: "run-1",
          project: body.project,
          stub_slug: body.stub_slug,
          status: "queued",
          target_run_count: body.target_ids.length,
          findings_count: 0,
          started_at: null,
          finished_at: null,
          created_at: "2026-05-19T00:00:00.000000Z",
        };
        scanRuns.push(run);
        return HttpResponse.json(run, { status: 201 });
      }),
      msw.get("/api/scan-runs/run-1/", () =>
        HttpResponse.json(scanRuns[0] ?? null),
      ),
      msw.get("/api/scan-runs/run-1/target-runs/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "tr1",
              scan_run: "run-1",
              target: "t1",
              target_base_url: "https://dvwa.cocode.dk",
              status: scanRuns[0]?.status ?? "queued",
              findings_count: 0,
              evidence_count: 0,
              started_at: null,
              finished_at: null,
            },
          ],
        }),
      ),
      msw.get("/api/scan-runs/run-1/findings/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/run-1/evidence/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.post("/api/scan-runs/run-1/start/", () => {
        scanRuns[0].status = "running";
        scanRuns[0].started_at = "2026-05-19T00:01:00.000000Z";
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<App />, { route: "/projects" });

    // Set as current
    await userEvent.click(
      await screen.findByRole("button", { name: /set as current/i }),
    );
    expect(window.localStorage.getItem("em.frontend.currentProjectId")).toBe(
      "p1",
    );

    // Sidebar → Targets → Add target
    await userEvent.click(screen.getByRole("link", { name: "Targets" }));
    await userEvent.click(
      await screen.findByTestId("page-header-create"),
    );
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    await waitFor(() =>
      expect(screen.getByText("https://dvwa.cocode.dk")).toBeInTheDocument(),
    );

    // Sidebar → Scan Runs → Create
    await userEvent.click(screen.getByRole("link", { name: "Scan Runs" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Create scan run" }),
    );
    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );

    // Lands on detail; click Start
    await screen.findByTestId("scan-run-header");
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() =>
      expect(scanRuns[0].status).toBe("running"),
    );

    // SSE emits an event → visible in live panel
    await waitFor(() => expect(lastSseInstance()).toBeDefined());
    act(() => {
      lastSseInstance()!.emit({
        id: "e1",
        scan_run_id: "run-1",
        target_id: "t1",
        level: "info",
        event_type: "target_started",
        message: "Started DVWA",
        data: {},
        created_at: "2026-05-19T00:01:01.000000Z",
      });
    });
    expect(screen.getByText("target_started")).toBeInTheDocument();
  });
});
