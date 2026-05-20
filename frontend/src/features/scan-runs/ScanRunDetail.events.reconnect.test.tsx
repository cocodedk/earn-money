import { describe, expect, it, vi, afterEach } from "vitest";
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
const NEW_EVENT_ID = "aaaaaaaa-bbbb-bbbb-bbbb-cccccccccccc";

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

function lastInstance(): MockEventSource {
  const arr = MockEventSource.instances;
  return arr[arr.length - 1];
}

afterEach(() => {
  vi.useRealTimers();
});

describe("ScanRunDetail — SSE disconnect-reconnect integration", () => {
  it(
    "fail → reconnecting → backoff opens new EventSource → connected → " +
      "emitted event renders",
    async () => {
      mountAt(ID);

      // 1. Wait until the SSE primary path reports `connected`.
      const pill = await screen.findByTestId("events-connection-status");
      await waitFor(() => expect(pill.textContent).toBe("connected"));
      expect(MockEventSource.instances.length).toBe(1);

      // 2. Switch to fake timers (shouldAdvanceTime keeps RQ polling alive so
      //    it doesn't deadlock the page's other panels).
      vi.useFakeTimers({ shouldAdvanceTime: true });

      // 3. First SSE failure → status flips to `reconnecting`.
      await act(async () => {
        lastInstance().fail();
        await Promise.resolve();
      });
      await waitFor(() => expect(pill.textContent).toBe("reconnecting"));

      // 4. Advance the first backoff window (1000ms) → a second EventSource
      //    instance is constructed by the reconnect effect.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(MockEventSource.instances.length).toBe(2);

      // 5. The new instance auto-opens on a microtask; drain it under fake
      //    timers, then assert the pill returns to `connected`.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      await waitFor(() => expect(pill.textContent).toBe("connected"));

      // 6. Emit a fixture event on the *new* instance → row appears.
      await act(async () => {
        lastInstance().emit(makeEvent({ id: NEW_EVENT_ID }));
        await Promise.resolve();
      });
      expect(
        await screen.findByTestId(`event-row-${NEW_EVENT_ID}`),
      ).toBeInTheDocument();
    },
  );
});
