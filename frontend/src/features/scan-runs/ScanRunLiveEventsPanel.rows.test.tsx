import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { ScanRunLiveEventsPanel } from "./ScanRunLiveEventsPanel";
import * as hookModule from "./useScanRunEvents";
import { makeEvent } from "./__fixtures__/event";
import {
  SCAN_RUN_ID,
  mockLiveEventsHook,
  renderLivePanel,
} from "./__fixtures__/livePanelMockHook";
import type { Event as ApiEvent, EventLevel } from "../../types/api";

vi.mock("./useScanRunEvents", () => ({ useScanRunEvents: vi.fn() }));

const TIME_RE = /^\d{1,2}:\d{2}:\d{2}/;

describe("ScanRunLiveEventsPanel — rows", () => {
  beforeEach(() => vi.mocked(hookModule.useScanRunEvents).mockReset());
  afterEach(() => vi.mocked(hookModule.useScanRunEvents).mockReset());

  it("renders 3 events in buffer order with correct columns", () => {
    mockLiveEventsHook("connected", [
      makeEvent({
        id: "aaaaaaaa-0000-0000-0000-000000000001",
        type: "target_started",
        message: "Started target A",
        target: "aaaaaaaa-1111-1111-1111-111111111111",
        level: "info",
      }),
      makeEvent({
        id: "aaaaaaaa-0000-0000-0000-000000000002",
        type: "target_finished",
        message: "Finished target B",
        target: "bbbbbbbb-2222-2222-2222-222222222222",
        level: "info",
      }),
      makeEvent({
        id: "aaaaaaaa-0000-0000-0000-000000000003",
        type: "scan_completed",
        message: "Scan completed",
        target: null,
        level: "warning",
      }),
    ]);
    renderLivePanel();

    const rows = screen.getAllByTestId(/^event-row-/);
    expect(rows).toHaveLength(3);

    const c0 = within(rows[0]).getAllByRole("cell");
    expect(c0[0].textContent).toMatch(TIME_RE);
    expect(c0[1].textContent).toBe("info");
    expect(c0[2].textContent).toBe("aaaaaaaa");
    expect(c0[3].textContent).toBe("target_started");
    expect(c0[4].textContent).toBe("Started target A");

    const c1 = within(rows[1]).getAllByRole("cell");
    expect(c1[2].textContent).toBe("bbbbbbbb");
    expect(c1[3].textContent).toBe("target_finished");
    expect(c1[4].textContent).toBe("Finished target B");

    const c2 = within(rows[2]).getAllByRole("cell");
    expect(c2[3].textContent).toBe("scan_completed");
    expect(c2[4].textContent).toBe("Scan completed");
  });

  it("renders '—' for null target", () => {
    const id = "aaaaaaaa-0000-0000-0000-00000000000a";
    mockLiveEventsHook("connected", [makeEvent({ id, target: null })]);
    renderLivePanel();
    const cells = within(screen.getByTestId(`event-row-${id}`)).getAllByRole(
      "cell",
    );
    expect(cells[2].textContent).toBe("—");
  });

  it("renders first 8 hex chars of UUID for non-null target", () => {
    const id = "aaaaaaaa-0000-0000-0000-00000000000b";
    mockLiveEventsHook("connected", [
      makeEvent({ id, target: "deadbeef-1234-5678-9abc-def012345678" }),
    ]);
    renderLivePanel();
    const cells = within(screen.getByTestId(`event-row-${id}`)).getAllByRole(
      "cell",
    );
    expect(cells[2].textContent).toBe("deadbeef");
  });

  it("applies expected colour class for each level", () => {
    const cases: Array<[EventLevel, string]> = [
      ["debug", "text-gray-600"],
      ["info", "text-blue-600"],
      ["warning", "text-amber-600"],
      ["error", "text-red-600"],
    ];
    for (const [level, expectedClass] of cases) {
      const id = `eeeeeeee-0000-0000-0000-00000000000${level[0]}`;
      mockLiveEventsHook("connected", [makeEvent({ id, level })]);
      const { unmount } = renderLivePanel();
      const cells = within(screen.getByTestId(`event-row-${id}`)).getAllByRole(
        "cell",
      );
      expect(cells[1].textContent).toBe(level);
      expect(cells[1].className).toContain(expectedClass);
      unmount();
    }
  });

  it("places event-row-{id} testid on every row", () => {
    const events = [
      makeEvent({ id: "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
      makeEvent({ id: "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb" }),
      makeEvent({ id: "33333333-cccc-cccc-cccc-cccccccccccc" }),
    ];
    mockLiveEventsHook("connected", events);
    renderLivePanel();
    for (const e of events) {
      expect(screen.getByTestId(`event-row-${e.id}`)).toBeInTheDocument();
    }
  });

  it("renders exactly 500 rows when hook returns 500 events (buffer-capped)", () => {
    const events: ApiEvent[] = [];
    for (let i = 0; i < 500; i++) {
      events.push(
        makeEvent({
          id: `cccccccc-0000-0000-0000-${i.toString().padStart(12, "0")}`,
        }),
      );
    }
    mockLiveEventsHook("connected", events);
    renderLivePanel();
    const rows = screen.getAllByTestId(/^event-row-/);
    expect(rows).toHaveLength(500);
    expect(rows[0].getAttribute("data-testid")).toBe(
      "event-row-cccccccc-0000-0000-0000-000000000000",
    );
    expect(rows[499].getAttribute("data-testid")).toBe(
      "event-row-cccccccc-0000-0000-0000-000000000499",
    );
  });

  it("re-renders only post-clear events when hook events array shrinks", () => {
    mockLiveEventsHook("connected", [
      makeEvent({ id: "ffffffff-0000-0000-0000-000000000001" }),
      makeEvent({ id: "ffffffff-0000-0000-0000-000000000002" }),
      makeEvent({ id: "ffffffff-0000-0000-0000-000000000003" }),
    ]);
    const { rerender } = renderLivePanel();
    expect(screen.getAllByTestId(/^event-row-/)).toHaveLength(3);

    mockLiveEventsHook("connected", [
      makeEvent({ id: "ffffffff-0000-0000-0000-00000000000a" }),
      makeEvent({ id: "ffffffff-0000-0000-0000-00000000000b" }),
    ]);
    rerender(
      <ScanRunLiveEventsPanel scanRunId={SCAN_RUN_ID} livePolling={true} />,
    );
    const rows = screen.getAllByTestId(/^event-row-/);
    expect(rows).toHaveLength(2);
    expect(rows[0].getAttribute("data-testid")).toBe(
      "event-row-ffffffff-0000-0000-0000-00000000000a",
    );
    expect(rows[1].getAttribute("data-testid")).toBe(
      "event-row-ffffffff-0000-0000-0000-00000000000b",
    );
    expect(
      screen.queryByTestId("event-row-ffffffff-0000-0000-0000-000000000001"),
    ).toBeNull();
  });
});
