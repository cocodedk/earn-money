import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ScanRunLiveEventsPanel } from "./ScanRunLiveEventsPanel";
import * as hookModule from "./useScanRunEvents";
import type {
  ConnectionStatus,
  UseScanRunEventsResult,
} from "./useScanRunEvents.utils";
import { makeEvent } from "./__fixtures__/event";
import type { Event as ApiEvent } from "../../types/api";

vi.mock("./useScanRunEvents", () => ({ useScanRunEvents: vi.fn() }));

const SCAN_RUN_ID = "11111111-1111-1111-1111-111111111111";

function mockHook(status: ConnectionStatus, events: ApiEvent[] = []) {
  const result: UseScanRunEventsResult = {
    events,
    status,
    reconnect: vi.fn(),
    clear: vi.fn(),
  };
  vi.mocked(hookModule.useScanRunEvents).mockReturnValue(result);
}

function renderPanel() {
  return renderWithProviders(
    <ScanRunLiveEventsPanel scanRunId={SCAN_RUN_ID} livePolling={true} />,
  );
}

const ALL_STATUSES: ConnectionStatus[] = [
  "connecting",
  "connected",
  "reconnecting",
  "polling-fallback",
  "closed",
  "disabled",
];

describe("ScanRunLiveEventsPanel — status indicator", () => {
  beforeEach(() => {
    vi.mocked(hookModule.useScanRunEvents).mockReset();
  });
  afterEach(() => {
    vi.mocked(hookModule.useScanRunEvents).mockReset();
  });

  it("renders title and status pill in every status", () => {
    for (const status of ALL_STATUSES) {
      mockHook(status);
      const { unmount } = renderPanel();
      expect(screen.getByText("Live events")).toBeInTheDocument();
      const pill = screen.getByTestId("events-connection-status");
      expect(pill.textContent).toBe(status);
      unmount();
    }
  });

  it("connecting + empty buffer → Connecting… hint, no table", () => {
    mockHook("connecting", []);
    renderPanel();
    expect(screen.getByTestId("events-connection-status").textContent).toBe(
      "connecting",
    );
    expect(screen.getByText("Connecting…")).toBeInTheDocument();
    expect(screen.queryByTestId("events-table")).toBeNull();
  });

  it("connected + empty → No events yet hint, no table", () => {
    mockHook("connected", []);
    renderPanel();
    expect(screen.getByText("No events yet")).toBeInTheDocument();
    expect(screen.queryByTestId("events-table")).toBeNull();
  });

  it("connected + 1 event → table renders, no hint", () => {
    mockHook("connected", [makeEvent({ id: "e1" })]);
    renderPanel();
    expect(screen.getByTestId("events-table")).toBeInTheDocument();
    expect(screen.getByTestId("events-connection-status").textContent).toBe(
      "connected",
    );
    expect(screen.queryByText("No events yet")).toBeNull();
    expect(screen.queryByText("Connecting…")).toBeNull();
  });

  it("reconnecting + 3 events → table still renders, no hint", () => {
    mockHook("reconnecting", [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
      makeEvent({ id: "e3" }),
    ]);
    renderPanel();
    expect(screen.getByTestId("events-table")).toBeInTheDocument();
    expect(screen.getByTestId("events-connection-status").textContent).toBe(
      "reconnecting",
    );
    expect(screen.queryByText("Reconnecting…")).toBeNull();
  });

  it("closed + 3 events → table still renders, no hint", () => {
    mockHook("closed", [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
      makeEvent({ id: "e3" }),
    ]);
    renderPanel();
    expect(screen.getByTestId("events-table")).toBeInTheDocument();
    expect(screen.getByTestId("events-connection-status").textContent).toBe(
      "closed",
    );
    expect(screen.queryByText("Disconnected")).toBeNull();
  });

  it("polling-fallback + events → table renders, pill shows polling-fallback", () => {
    mockHook("polling-fallback", [makeEvent({ id: "e1" })]);
    renderPanel();
    expect(screen.getByTestId("events-table")).toBeInTheDocument();
    expect(screen.getByTestId("events-connection-status").textContent).toBe(
      "polling-fallback",
    );
  });

  it("disabled + empty → kill-switch hint shown, no table, pill disabled", () => {
    mockHook("disabled", []);
    renderPanel();
    expect(screen.getByTestId("events-connection-status").textContent).toBe(
      "disabled",
    );
    expect(
      screen.getByText(/Live events disabled/),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("events-table")).toBeNull();
  });
});
