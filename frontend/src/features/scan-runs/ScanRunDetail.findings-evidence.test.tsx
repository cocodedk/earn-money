import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withBareArray, withPaginated } from "../../test/helpers";
import { scanRunKey } from "./api";
import { ScanRunDetail } from "./ScanRunDetail";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import { makeFinding } from "./__fixtures__/finding";
import { makeEvidence } from "./__fixtures__/evidence";
import type { ScanRun } from "../../types/api";

const ID = "11111111-1111-1111-1111-111111111111";

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

describe("ScanRunDetail findings + evidence panels", () => {
  it("renders Findings panel below targets table", async () => {
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () =>
        HttpResponse.json(makeScanRun({ id: ID, status: "done" })),
      ),
    );
    mountAt(ID);
    expect(await screen.findByText(/Findings \(0\)/)).toBeInTheDocument();
  });

  it("happy path: renders 2 findings + 3 evidence with headings", async () => {
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () =>
        HttpResponse.json(makeScanRun({ id: ID, status: "done" })),
      ),
      msw.get("/api/findings/", () =>
        HttpResponse.json({
          count: 2,
          next: null,
          previous: null,
          results: [
            makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaa1" }),
            makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaa2" }),
          ],
        }),
      ),
      msw.get("/api/evidence/", () =>
        HttpResponse.json({
          count: 3,
          next: null,
          previous: null,
          results: [
            makeEvidence({ id: "eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbb1" }),
            makeEvidence({ id: "eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbb2" }),
            makeEvidence({ id: "eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbb3" }),
          ],
        }),
      ),
    );
    mountAt(ID);
    const findingRows = await screen.findAllByTestId(/^finding-row-/);
    expect(findingRows).toHaveLength(2);
    const evidenceRows = await screen.findAllByTestId(/^evidence-row-/);
    expect(evidenceRows).toHaveLength(3);
    expect(await screen.findByText(/Findings \(2\)/)).toBeInTheDocument();
    expect(await screen.findByText(/Evidence \(3\)/)).toBeInTheDocument();
  });

  it("both panels poll while running: new finding appears on next tick", async () => {
    vi.useFakeTimers();
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () =>
        HttpResponse.json(makeScanRun({ id: ID, status: "running" })),
      ),
      msw.get("/api/findings/", () =>
        HttpResponse.json({
          count: phase === "pre" ? 0 : 1,
          next: null,
          previous: null,
          results:
            phase === "pre"
              ? []
              : [makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa" })],
        }),
      ),
    );
    mountAt(ID);
    await vi.advanceTimersByTimeAsync(500); // initial fetch settles
    phase = "post";
    await vi.advanceTimersByTimeAsync(2100); // one poll tick past 2s
    vi.useRealTimers();
    await screen.findByTestId("finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
  });

  it("terminal flush: both panels each refetch once after parent flips to done", async () => {
    vi.useFakeTimers();
    let scanRun: ScanRun = makeScanRun({ id: ID, status: "running" });
    let fcalls = 0;
    let ecalls = 0;
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () => HttpResponse.json(scanRun)),
      msw.get("/api/findings/", () => {
        fcalls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
      msw.get("/api/evidence/", () => {
        ecalls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { client } = mountAt(ID);
    // Let initial fetches settle without crossing the 2s poll boundary.
    await vi.advanceTimersByTimeAsync(500);
    const before = { f: fcalls, e: ecalls };
    expect(before.f).toBe(1);
    expect(before.e).toBe(1);
    scanRun = makeScanRun({ id: ID, status: "done" });
    // exact: true so we don't prefix-invalidate child keys; the panels'
    // livePolling true→false flush is what should cause exactly one extra fetch.
    await client.invalidateQueries({ queryKey: scanRunKey(ID), exact: true });
    await vi.advanceTimersByTimeAsync(100);
    vi.useRealTimers();
    await waitFor(() => expect(fcalls).toBe(before.f + 1));
    await waitFor(() => expect(ecalls).toBe(before.e + 1));
  });

  it("error on 500: both panels show 'Could not load' callouts", async () => {
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () =>
        HttpResponse.json(makeScanRun({ id: ID, status: "done" })),
      ),
      msw.get("/api/findings/", () => HttpResponse.error()),
      msw.get("/api/evidence/", () => HttpResponse.error()),
    );
    mountAt(ID);
    const callouts = await screen.findAllByText(/Could not load/);
    expect(callouts.length).toBeGreaterThanOrEqual(2);
  });
});
