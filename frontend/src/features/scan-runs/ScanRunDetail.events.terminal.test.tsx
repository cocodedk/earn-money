import {
  describe,
  expect,
  it,
  vi,
  afterEach,
} from "vitest";
import { act, screen, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withBareArray, withPaginated } from "../../test/helpers";
import { MockEventSource } from "../../test/sseMock";
import { scanRunKey } from "./api";
import { ScanRunDetail } from "./ScanRunDetail";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import { makeEvent } from "./__fixtures__/event";
import type { ScanRun } from "../../types/api";

const ID = "11111111-1111-1111-1111-111111111111";
const EVT = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaa1";

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

async function emitOneEvent(message: string): Promise<void> {
  await waitFor(() =>
    expect(MockEventSource.instances.length).toBeGreaterThan(0),
  );
  const es = MockEventSource.instances[0];
  await waitFor(() => expect(es.readyState).toBe(1));
  await act(async () => {
    es.emit(makeEvent({ id: EVT, message }));
  });
  await screen.findByTestId(`event-row-${EVT}`);
}

afterEach(() => {
  vi.useRealTimers();
  localStorage.removeItem("disable_live_events");
});

describe("ScanRunDetail SSE — terminal + pause + kill-switch", () => {
  it("terminal cleanup: running→done flips status to closed; buffered row stays", async () => {
    let run: ScanRun = makeScanRun({ id: ID, status: "running" });
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () => HttpResponse.json(run)),
    );
    const { client } = mountAt(ID);
    await emitOneEvent("buffered-before-terminal");

    run = makeScanRun({ id: ID, status: "done" });
    await act(async () => {
      await client.invalidateQueries({ queryKey: scanRunKey(ID), exact: true });
    });

    await waitFor(() =>
      expect(screen.getByTestId("events-connection-status")).toHaveTextContent(
        "closed",
      ),
    );
    expect(screen.getByTestId(`event-row-${EVT}`)).toBeInTheDocument();
  });

  it("pause/resume: running→paused→running closes then reopens SSE; row persists", async () => {
    let run: ScanRun = makeScanRun({ id: ID, status: "running" });
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () => HttpResponse.json(run)),
    );
    const { client } = mountAt(ID);
    await emitOneEvent("survives-pause-resume");
    const openedWhileRunning = MockEventSource.instances.length;

    run = makeScanRun({ id: ID, status: "paused" });
    await act(async () => {
      await client.invalidateQueries({ queryKey: scanRunKey(ID), exact: true });
    });
    await waitFor(() =>
      expect(screen.getByTestId("events-connection-status")).toHaveTextContent(
        "closed",
      ),
    );
    expect(screen.getByTestId(`event-row-${EVT}`)).toBeInTheDocument();

    run = makeScanRun({ id: ID, status: "running" });
    await act(async () => {
      await client.invalidateQueries({ queryKey: scanRunKey(ID), exact: true });
    });
    await waitFor(() =>
      expect(MockEventSource.instances.length).toBeGreaterThan(
        openedWhileRunning,
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("events-connection-status")).toHaveTextContent(
        "connected",
      ),
    );
    expect(screen.getByTestId(`event-row-${EVT}`)).toBeInTheDocument();
  });

  it("kill switch: localStorage flag blocks SSE, status disabled, hint shown", async () => {
    localStorage.setItem("disable_live_events", "1");
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () =>
        HttpResponse.json(makeScanRun({ id: ID, status: "running" })),
      ),
    );
    mountAt(ID);

    await waitFor(() =>
      expect(screen.getByTestId("events-connection-status")).toHaveTextContent(
        "disabled",
      ),
    );
    expect(screen.getByText(/Live events disabled/)).toBeInTheDocument();
    expect(screen.queryByTestId(new RegExp("^event-row-"))).toBeNull();
    expect(MockEventSource.instances.length).toBe(0);
  });
});
