import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EventList } from "./EventList";
import type { ScanEvent } from "../../types/api";

const events: ScanEvent[] = [
  {
    id: "e1",
    scan_run_id: "r1",
    target_id: "t1",
    level: "info",
    event_type: "target_started",
    message: "Started",
    data: {},
    created_at: "2026-05-18T20:00:00.000000Z",
  },
  {
    id: "e2",
    scan_run_id: "r1",
    target_id: "t1",
    level: "error",
    event_type: "scan_target_run.failed",
    message: "Boom",
    data: {},
    created_at: "2026-05-18T20:00:05.000000Z",
  },
  {
    id: "e3",
    scan_run_id: "r1",
    target_id: "t1",
    level: "debug",
    event_type: "trace",
    message: "Hidden",
    data: {},
    created_at: "2026-05-18T20:00:01.000000Z",
  },
];

describe("EventList", () => {
  it("renders each event with timestamp, level, type, message", () => {
    render(<EventList events={events} />);
    const rows = screen.getAllByTestId("event-row");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("info");
    expect(rows[0]).toHaveTextContent("target_started");
    expect(rows[1]).toHaveTextContent("error");
    expect(rows[1]).toHaveTextContent("Boom");
  });

  it("filters by minimum level when filter is set", async () => {
    render(<EventList events={events} />);
    await userEvent.selectOptions(screen.getByLabelText("Level"), "error");
    const rows = screen.getAllByTestId("event-row");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("error");
  });

  it("renders the empty state when no events", () => {
    render(<EventList events={[]} />);
    expect(screen.getByText(/no events/i)).toBeInTheDocument();
  });

  it("renders the empty state when filter excludes everything", async () => {
    render(<EventList events={[events[0]]} />);
    await userEvent.selectOptions(screen.getByLabelText("Level"), "error");
    expect(screen.getByText(/no events/i)).toBeInTheDocument();
  });

  it("toggles auto-scroll", async () => {
    render(<EventList events={events} />);
    const toggle = screen.getByRole("checkbox", { name: /auto-scroll/i });
    expect(toggle).toBeChecked();
    await userEvent.click(toggle);
    expect(toggle).not.toBeChecked();
  });
});
