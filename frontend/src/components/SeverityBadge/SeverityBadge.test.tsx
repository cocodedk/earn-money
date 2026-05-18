import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeverityBadge } from "./SeverityBadge";

describe("SeverityBadge", () => {
  it.each([
    ["info", "Info"],
    ["low", "Low"],
    ["medium", "Medium"],
    ["high", "High"],
    ["critical", "Critical"],
  ] as const)("renders the %s severity", (severity, label) => {
    render(<SeverityBadge severity={severity} />);
    const badge = screen.getByTestId("severity-badge");
    expect(badge).toHaveAttribute("data-severity", severity);
    expect(badge).toHaveTextContent(label);
  });
});
