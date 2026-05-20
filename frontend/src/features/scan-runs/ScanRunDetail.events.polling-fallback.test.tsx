import { describe, it, expect, afterEach, vi } from "vitest";
import { act, screen, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withBareArray, withPaginated } from "../../test/helpers";
import { MockEventSource } from "../../test/sseMock";
import { ScanRunDetail } from "./ScanRunDetail";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import { makeEvent } from "./__fixtures__/event";

const ID = "11111111-1111-1111-1111-111111111111";
const BACKOFFS = [1000, 2000, 4000, 8000, 16000];

function mountAt(id: string) {
  withPaginated("/api/projects/", []);
  withBareArray("/api/stubs/", [makeStub()]);
  server.use(
    msw.get(`/api/scan-runs/${id}/`, () =>
      HttpResponse.json(makeScanRun({ id, status: "running" })),
    ),
  );
  return renderWithProviders(
    <Routes>
      <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
    </Routes>,
    { route: `/scan-runs/${id}` },
  );
}

async function flushReactUpdates() {
  await act(async () => {
    await Promise.resolve();
  });
}

async function enterPollingFallback() {
  // Wait until the first EventSource is created and opens (real timers).
  await waitFor(() =>
    expect(MockEventSource.instances.length).toBeGreaterThan(0),
  );
  await waitFor(() => expect(MockEventSource.instances[0].readyState).toBe(1));

  vi.useFakeTimers({ shouldAdvanceTime: true });
  MockEventSource.autoOpen = false;
  for (let i = 0; i < BACKOFFS.length; i += 1) {
    const inst = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => inst.fail());
    await flushReactUpdates();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(BACKOFFS[i]);
    });
  }
  const last = MockEventSource.instances[MockEventSource.instances.length - 1];
  act(() => last.fail());
  await flushReactUpdates();
}

afterEach(() => {
  vi.useRealTimers();
});

describe("ScanRunDetail SSE polling-fallback integration", () => {
  it("flips status pill to polling-fallback and renders rows from REST", async () => {
    server.use(
      msw.get(`/api/scan-runs/${ID}/events/`, () =>
        HttpResponse.json({
          count: 2,
          next: null,
          previous: null,
          results: [
            makeEvent({ id: "p1", message: "Poll one" }),
            makeEvent({ id: "p2", message: "Poll two" }),
          ],
        }),
      ),
    );
    mountAt(ID);
    await enterPollingFallback();

    await waitFor(() =>
      expect(screen.getByTestId("events-connection-status")).toHaveTextContent(
        "polling-fallback",
      ),
    );

    // Advance one polling interval — the tick should fire the REST fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    // Settle the pending fetch microtasks/MSW resolution.
    await vi.waitFor(() =>
      expect(screen.getByTestId("event-row-p1")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("event-row-p2")).toBeInTheDocument();
  });

  it("dedupes overlapping ids across consecutive polling ticks", async () => {
    let phase: "first" | "second" = "first";
    server.use(
      msw.get(`/api/scan-runs/${ID}/events/`, () => {
        if (phase === "first") {
          return HttpResponse.json({
            count: 2,
            next: null,
            previous: null,
            results: [
              makeEvent({ id: "d1", message: "First" }),
              makeEvent({ id: "d2", message: "Second" }),
            ],
          });
        }
        return HttpResponse.json({
          count: 2,
          next: null,
          previous: null,
          results: [
            // Overlap on d2; d3 is new.
            makeEvent({ id: "d2", message: "Second" }),
            makeEvent({ id: "d3", message: "Third" }),
          ],
        });
      }),
    );
    mountAt(ID);
    await enterPollingFallback();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    await vi.waitFor(() =>
      expect(screen.getByTestId("event-row-d1")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("event-row-d2")).toBeInTheDocument();

    phase = "second";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    await vi.waitFor(() =>
      expect(screen.getByTestId("event-row-d3")).toBeInTheDocument(),
    );

    // Dedupe: only 3 rows total (d1, d2, d3) — not 4.
    const rows = screen.getAllByTestId(/^event-row-/);
    expect(rows).toHaveLength(3);
  });
});
