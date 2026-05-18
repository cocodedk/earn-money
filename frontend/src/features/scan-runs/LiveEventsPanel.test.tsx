import { describe, it, expect } from "vitest";
import { render, act, waitFor, screen } from "@testing-library/react";
import { lastSseInstance } from "../../test/sseMock";
import { LiveEventsPanel } from "./LiveEventsPanel";

const sampleEvent = {
  id: "e1",
  scan_run_id: "r1",
  target_id: "t1",
  level: "info",
  event_type: "target_started",
  message: "Started",
  data: {},
  created_at: "2026-05-18T20:00:00.000000Z",
};

describe("LiveEventsPanel", () => {
  it("streams events through to EventList", async () => {
    render(<LiveEventsPanel scanRunId="r1" />);
    await waitFor(() => expect(lastSseInstance()).toBeDefined());
    act(() => {
      lastSseInstance()!.emit(sampleEvent);
    });
    expect(screen.getByText("target_started")).toBeInTheDocument();
  });

  it("surfaces the connection status as data-status", async () => {
    render(<LiveEventsPanel scanRunId="r1" />);
    await waitFor(() =>
      expect(screen.getByTestId("live-events-panel")).toHaveAttribute(
        "data-status",
        "open",
      ),
    );
  });
});
