import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TargetRunsTable } from "./TargetRunsTable";

describe("TargetRunsTable", () => {
  it("renders rows with status badge + timestamps", () => {
    render(
      <TargetRunsTable
        rows={[
          {
            id: "tr1",
            scan_run: "r1",
            target: "t1",
            target_base_url: "https://dvwa.cocode.dk",
            status: "running",
            findings_count: 0,
            evidence_count: 0,
            started_at: "2026-05-18T20:01:00.000000Z",
            finished_at: null,
          },
        ]}
      />,
    );
    expect(screen.getByText("https://dvwa.cocode.dk")).toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveAttribute(
      "data-status",
      "running",
    );
    expect(screen.getByText("20:01:00")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders the loading skeleton", () => {
    render(<TargetRunsTable rows={[]} isLoading />);
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("renders the empty state when no rows", () => {
    render(<TargetRunsTable rows={[]} />);
    expect(screen.getByText(/no target runs yet/i)).toBeInTheDocument();
  });
});
