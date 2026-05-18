import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScanRunHeader } from "./ScanRunHeader";

describe("ScanRunHeader", () => {
  it("renders the scan run fields with a status badge", () => {
    render(
      <ScanRunHeader
        scanRun={{
          id: "r1",
          project: "p1",
          stub_slug: "1.1",
          status: "running",
          target_run_count: 0,
          findings_count: 0,
          started_at: "2026-05-18T20:00:00.000000Z",
          finished_at: null,
          created_at: "2026-05-18T20:00:00.000000Z",
        }}
      />,
    );
    expect(screen.getByText("r1")).toBeInTheDocument();
    expect(screen.getByText("p1")).toBeInTheDocument();
    expect(screen.getByText("1.1")).toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveAttribute(
      "data-status",
      "running",
    );
    expect(screen.getByText("2026-05-18 20:00:00")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
