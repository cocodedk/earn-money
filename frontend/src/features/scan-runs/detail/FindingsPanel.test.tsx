import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FindingsPanel } from "./FindingsPanel";

describe("FindingsPanel", () => {
  it("renders findings with severity badge", () => {
    render(
      <FindingsPanel
        rows={[
          {
            id: "f1",
            scan_run: "r1",
            target: "t1abcdef",
            stub_slug: "1.1",
            title: "Express detected",
            category: "framework-detection",
            severity: "info",
            confidence: "high",
            status: "candidate",
            data: {},
            created_at: "2026-05-18T20:00:00.000000Z",
            updated_at: "2026-05-18T20:00:00.000000Z",
          },
        ]}
      />,
    );
    expect(screen.getByText("Express detected")).toBeInTheDocument();
    expect(screen.getByTestId("severity-badge")).toHaveAttribute(
      "data-severity",
      "info",
    );
  });

  it("renders empty state", () => {
    render(<FindingsPanel rows={[]} />);
    expect(screen.getByText(/no findings yet/i)).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    render(<FindingsPanel rows={[]} isLoading />);
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });
});
