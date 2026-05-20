import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as hookModule from "./useScanRunEvents";
import type { ConnectionStatus } from "./useScanRunEvents.utils";
import { makeEvent } from "./__fixtures__/event";
import {
  mockLiveEventsHook,
  renderLivePanel,
} from "./__fixtures__/livePanelMockHook";

vi.mock("./useScanRunEvents", () => ({ useScanRunEvents: vi.fn() }));

const CLEAR = "events-clear-local";
const RECONNECT = "events-reconnect";

const KILL_SWITCH_TITLE =
  "Live events disabled by kill switch — remove localStorage.disable_live_events and reload to re-enable.";

const ALL_STATUSES: ConnectionStatus[] = [
  "connecting",
  "connected",
  "reconnecting",
  "polling-fallback",
  "closed",
  "disabled",
];

const RECONNECT_ENABLED: ConnectionStatus[] = [
  "connecting",
  "connected",
  "reconnecting",
  "polling-fallback",
];

describe("ScanRunLiveEventsPanel — clear + reconnect controls", () => {
  beforeEach(() => vi.mocked(hookModule.useScanRunEvents).mockReset());
  afterEach(() => vi.mocked(hookModule.useScanRunEvents).mockReset());

  it("clear button calls clear() and is enabled in every status", async () => {
    const user = userEvent.setup();
    // 'closed' and 'disabled' would disable reconnect; clear must stay enabled.
    for (const status of ["closed", "disabled"] as ConnectionStatus[]) {
      const { clear } = mockLiveEventsHook(status, [makeEvent({ id: "e1" })]);
      const { unmount } = renderLivePanel();
      const btn = screen.getByTestId(CLEAR);
      expect(btn).not.toBeDisabled();
      await user.click(btn);
      expect(clear).toHaveBeenCalledTimes(1);
      unmount();
    }
  });

  it.each(RECONNECT_ENABLED)(
    "reconnect button in %s status is enabled and calls reconnect()",
    async (status) => {
      const user = userEvent.setup();
      const { reconnect } = mockLiveEventsHook(status, []);
      renderLivePanel();
      const btn = screen.getByTestId(RECONNECT);
      expect(btn).not.toBeDisabled();
      await user.click(btn);
      expect(reconnect).toHaveBeenCalledTimes(1);
    },
  );

  it("reconnect button in closed status is disabled; click does not call reconnect()", async () => {
    const user = userEvent.setup();
    const { reconnect } = mockLiveEventsHook("closed", []);
    renderLivePanel();
    const btn = screen.getByTestId(RECONNECT);
    expect(btn).toBeDisabled();
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    await user.click(btn).catch(() => {});
    expect(reconnect).toHaveBeenCalledTimes(0);
  });

  it("reconnect button in disabled status is disabled with kill-switch tooltip", async () => {
    const user = userEvent.setup();
    const { reconnect } = mockLiveEventsHook("disabled", []);
    renderLivePanel();
    const btn = screen.getByTestId(RECONNECT);
    expect(btn).toBeDisabled();
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    expect(btn.getAttribute("title")).toBe(KILL_SWITCH_TITLE);
    await user.click(btn).catch(() => {});
    expect(reconnect).toHaveBeenCalledTimes(0);
  });

  it("both clear and reconnect buttons present in all 6 statuses", () => {
    for (const status of ALL_STATUSES) {
      mockLiveEventsHook(status, []);
      const { unmount } = renderLivePanel();
      expect(screen.getByTestId(CLEAR)).toBeInTheDocument();
      expect(screen.getByTestId(RECONNECT)).toBeInTheDocument();
      unmount();
    }
  });
});
