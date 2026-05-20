import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withBareArray, withPaginated } from "../../test/helpers";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import { ScanRunDetail } from "./ScanRunDetail";

const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 1,
  scan_run_count: 1,
  created_at: "2026-05-19T08:00:00.000000Z",
};

function withDeps() {
  withPaginated("/api/projects/", [PROJECT]);
  withBareArray("/api/stubs/", [makeStub()]);
}

function renderAt(path: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
    </Routes>,
    { route: path },
  );
}

describe("ScanRunDetail — branches", () => {
  it("shows the loading header before data resolves", async () => {
    withDeps();
    server.use(msw.get("/api/scan-runs/r-1/", () => new Promise(() => {})));
    renderAt("/scan-runs/r-1");
    expect(await screen.findByText("Loading…")).toBeInTheDocument();
  });

  it("renders Scan run not found on 404 with a back link", async () => {
    withDeps();
    server.use(
      msw.get("/api/scan-runs/r-missing/", () =>
        HttpResponse.json({ detail: "No scan run" }, { status: 404 }),
      ),
    );
    renderAt("/scan-runs/r-missing");
    expect(await screen.findByText(/scan run not found/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /back to scan runs/i }),
    ).toHaveAttribute("href", "/scan-runs");
  });

  it("renders Backend-unreachable on transport error", async () => {
    withDeps();
    server.use(msw.get("/api/scan-runs/r-1/", () => HttpResponse.error()));
    renderAt("/scan-runs/r-1");
    expect(
      await screen.findByText(/backend unreachable/i),
    ).toBeInTheDocument();
  });
});

describe("ScanRunDetail — happy paths", () => {
  it("renders header + project + stub joined + Start button on queued", async () => {
    withDeps();
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(makeScanRun())),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderAt("/scan-runs/r-1");
    expect(await screen.findByText(/Scan run · r-1/)).toBeInTheDocument();
    expect(await screen.findByText("Local Lab")).toBeInTheDocument();
    expect(screen.getByText("1.1")).toBeInTheDocument();
    expect(screen.getByTestId("status-queued")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Pause" }),
    ).not.toBeInTheDocument();
  });

  it("renders Pause + Stop on running and hides Start + Resume", async () => {
    withDeps();
    server.use(
      msw.get("/api/scan-runs/r-1/", () =>
        HttpResponse.json(
          makeScanRun({ status: "running", started_at: "2026-05-19T09:00:00.000Z" }),
        ),
      ),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderAt("/scan-runs/r-1");
    await screen.findByTestId("status-running");
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Resume" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("2026-05-19T09:00:00")).toBeInTheDocument();
  });

  it("renders no lifecycle buttons on done + shows finished_at", async () => {
    withDeps();
    server.use(
      msw.get("/api/scan-runs/r-1/", () =>
        HttpResponse.json(
          makeScanRun({
            status: "done",
            started_at: "2026-05-19T09:00:00.000Z",
            finished_at: "2026-05-19T09:05:30.000Z",
          }),
        ),
      ),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderAt("/scan-runs/r-1");
    await screen.findByTestId("status-done");
    for (const label of ["Start", "Pause", "Resume", "Stop"]) {
      expect(
        screen.queryByRole("button", { name: label }),
      ).not.toBeInTheDocument();
    }
    expect(screen.getByText("2026-05-19T09:05:30")).toBeInTheDocument();
  });

  it("renders em-dash for null started_at and finished_at", async () => {
    withDeps();
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(makeScanRun())),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderAt("/scan-runs/r-1");
    await screen.findByTestId("status-queued");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("clicking Start fires the start mutation", async () => {
    withDeps();
    let hit = false;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(makeScanRun())),
      msw.post("/api/scan-runs/r-1/start/", () => {
        hit = true;
        return HttpResponse.json(makeScanRun({ status: "running" }));
      }),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderAt("/scan-runs/r-1");
    await screen.findByTestId("status-queued");
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(hit).toBe(true));
  });
});
