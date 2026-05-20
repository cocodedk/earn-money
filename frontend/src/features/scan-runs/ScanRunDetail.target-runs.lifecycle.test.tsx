import { describe, it, expect, vi } from "vitest";
import { screen, within, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withBareArray, withPaginated } from "../../test/helpers";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import type { ScanRun } from "../../types/api";
import { ScanRunDetail } from "./ScanRunDetail";

function mountAt(id: string) {
  withPaginated("/api/projects/", []);
  withBareArray("/api/stubs/", [makeStub()]);
  return renderWithProviders(
    <Routes>
      <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
    </Routes>,
    { route: `/scan-runs/${id}` },
  );
}

describe("ScanRunDetail target-runs lifecycle + silent error", () => {
  // --- group 3: cascade + visible polling ---
  it("lifecycle stop-from-paused cascade refetches target-runs", async () => {
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "paused" });
    let targetCalls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
        targetCalls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
      msw.post("/api/scan-runs/r-1/stop/", () => {
        parent = makeScanRun({ id: "r-1", status: "stopping" });
        return HttpResponse.json(parent);
      }),
    );
    mountAt("r-1");
    await screen.findByTestId("targets-empty");
    const before = targetCalls;
    (await screen.findByRole("button", { name: /stop/i })).click();
    await waitFor(() => expect(targetCalls).toBeGreaterThan(before));
  });

  it("visible badge update on poll (within 2 s)", async () => {
    vi.useFakeTimers();
    let target = makeScanTargetRun({ id: "tr-1", status: "queued" });
    server.use(
      msw.get("/api/scan-runs/r-1/", () =>
        HttpResponse.json(makeScanRun({ id: "r-1", status: "running" })),
      ),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [target] }),
      ),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(100); // initial fetch settles
    target = makeScanTargetRun({ id: "tr-1", status: "running" });
    await vi.advanceTimersByTimeAsync(2500); // poll fires with new status
    vi.useRealTimers();
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      const badge = within(row).getByTestId("status-running");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent("running");
    });
  });

  // --- group 4: background error silence ---
  it("parent background 500 → page stays mounted, no full-page takeover", async () => {
    let serveError = false;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => {
        if (serveError) return new HttpResponse(null, { status: 500 });
        return HttpResponse.json(makeScanRun({ id: "r-1", status: "running" }));
      }),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1" })],
        }),
      ),
    );
    mountAt("r-1");
    await screen.findByTestId("target-run-row-tr-1");
    serveError = true;
    await new Promise((r) => setTimeout(r, 2500));
    expect(screen.getByText(/Scan run · r-1/)).toBeInTheDocument();
    expect(screen.getByTestId("target-run-row-tr-1")).toBeInTheDocument();
    expect(screen.queryByText(/backend unreachable/i)).not.toBeInTheDocument();
  });

  it("parent background 404 → page stays mounted, no not-found takeover", async () => {
    let serve404 = false;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => {
        if (serve404) return new HttpResponse(null, { status: 404 });
        return HttpResponse.json(makeScanRun({ id: "r-1", status: "running" }));
      }),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1" })],
        }),
      ),
    );
    mountAt("r-1");
    await screen.findByTestId("target-run-row-tr-1");
    serve404 = true;
    await new Promise((r) => setTimeout(r, 2500));
    expect(screen.getByText(/Scan run · r-1/)).toBeInTheDocument();
    expect(screen.getByTestId("target-run-row-tr-1")).toBeInTheDocument();
    expect(screen.queryByText(/not found/i)).not.toBeInTheDocument();
  });
});
