import { describe, it, expect, vi } from "vitest";
import { screen, within, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse, delay } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withBareArray, withPaginated } from "../../test/helpers";
import { scanRunKey } from "./api";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import type { ScanRun } from "../../types/api";
import { ScanRunDetail } from "./ScanRunDetail";

function mountAt(id: string) {
  // renderWithProviders already wraps in MemoryRouter + QueryClientProvider
  // and returns the test `client` for invalidation/seeding from the test.
  withPaginated("/api/projects/", []);
  withBareArray("/api/stubs/", [makeStub()]);
  return renderWithProviders(
    <Routes>
      <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
    </Routes>,
    { route: `/scan-runs/${id}` },
  );
}

describe("ScanRunDetail target-runs integration", () => {
  // --- group 1: happy + parent-driven transitions ---
  it("renders the table beneath the MetaList on happy detail load", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/", () =>
        HttpResponse.json(makeScanRun({ id: "r-1", status: "running" })),
      ),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: "queued" })],
        }),
      ),
    );
    mountAt("r-1");
    expect(await screen.findByTestId("target-run-row-tr-1")).toBeInTheDocument();
  });

  it("parent queued → running: table starts polling", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "queued" });
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
        calls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { client } = mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500);
    const beforeFlip = calls;
    parent = makeScanRun({ id: "r-1", status: "running" });
    await client.invalidateQueries({ queryKey: scanRunKey("r-1") });
    await vi.advanceTimersByTimeAsync(3000);
    vi.useRealTimers();
    await waitFor(() => expect(calls).toBeGreaterThan(beforeFlip));
  });

  it("parent running → done: cache ends with fresh terminal rows (terminal flush)", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "running" });
    let target = makeScanTargetRun({ id: "tr-1", status: "running" });
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [target] }),
      ),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500);
    parent = makeScanRun({ id: "r-1", status: "done" });
    target = makeScanTargetRun({ id: "tr-1", status: "done" });
    await vi.advanceTimersByTimeAsync(3000); // parent flips, flush fires
    vi.useRealTimers();
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      expect(within(row).getByTestId("status-done")).toBeInTheDocument();
    });
  });

  it("parent running → stopping → stopped: same cache-content assertion shape", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "running" });
    let target = makeScanTargetRun({ id: "tr-1", status: "running" });
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [target] }),
      ),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500);
    parent = makeScanRun({ id: "r-1", status: "stopping" });
    await vi.advanceTimersByTimeAsync(2500);
    parent = makeScanRun({ id: "r-1", status: "stopped" });
    target = makeScanTargetRun({
      id: "tr-1", status: "stopped", finished_at: "2026-05-19T10:00:00Z",
    });
    await vi.advanceTimersByTimeAsync(3000);
    vi.useRealTimers();
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      expect(within(row).getByTestId("status-stopped")).toBeInTheDocument();
    });
  });

  // --- group 2: terminal-flush in-flight branches ---
  it("in-flight flush — cached data exists: cache ends fresh", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "running" });
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", async () => {
        if (phase === "pre") {
          return HttpResponse.json({
            count: 1, next: null, previous: null,
            results: [makeScanTargetRun({ id: "tr-1", status: "running" })],
          });
        }
        await delay(200);
        return HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: "done" })],
        });
      }),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500); // cached "running" landed
    phase = "post";
    parent = makeScanRun({ id: "r-1", status: "done" });
    await vi.advanceTimersByTimeAsync(2000); // parent polls done, flush fires while child is in-flight
    await vi.advanceTimersByTimeAsync(500);
    vi.useRealTimers();
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      expect(within(row).getByTestId("status-done")).toBeInTheDocument();
    });
  });

  it("no-cached-data in-flight at terminal flip: cache ends fresh (round-5 edge case)", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "running" });
    let delayMs = 800; // initial fetch slow
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", async () => {
        await delay(delayMs);
        return HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({
            id: "tr-1", status: parent.status === "done" ? "done" : "running",
          })],
        });
      }),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(100); // initial fetch in flight, no cached data
    parent = makeScanRun({ id: "r-1", status: "done" });
    delayMs = 0;
    await vi.advanceTimersByTimeAsync(3000);
    vi.useRealTimers();
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      expect(within(row).getByTestId("status-done")).toBeInTheDocument();
    });
  });
});
