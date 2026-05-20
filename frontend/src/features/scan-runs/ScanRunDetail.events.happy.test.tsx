import { describe, expect, it } from "vitest";
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

describe("ScanRunDetail SSE happy path", () => {
  it("opens SSE for a running run and renders an emitted event row", async () => {
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () =>
        HttpResponse.json(makeScanRun({ id: ID, status: "running" })),
      ),
    );
    mountAt(ID);

    // Panel mounts (and hook wires SSE) once the scan run resolves.
    expect(
      await screen.findByTestId("events-connection-status"),
    ).toBeInTheDocument();

    await waitFor(() =>
      expect(MockEventSource.instances.length).toBeGreaterThan(0),
    );

    const instance = MockEventSource.instances[0];
    expect(instance.url).toBe(`/sse/scan-runs/${ID}/events/`);
    await waitFor(() => expect(instance.readyState).toBe(1));

    const eventId = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaa1";
    act(() => {
      instance.emit(makeEvent({ id: eventId, message: "Hello SSE" }));
    });

    const row = await screen.findByTestId(`event-row-${eventId}`);
    expect(row).toHaveTextContent("Hello SSE");
  });
});
