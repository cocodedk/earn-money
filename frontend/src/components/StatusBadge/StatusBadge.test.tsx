import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["queued", "Queued"],
    ["running", "Running"],
    ["paused", "Paused"],
    ["stopping", "Stopping"],
    ["stopped", "Stopped"],
    ["failed", "Failed"],
    ["done", "Done"],
    ["active", "Active"],
    ["retired", "Retired"],
  ] as const)("renders the %s status", (status, label) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByTestId("status-badge");
    expect(badge).toHaveAttribute("data-status", status);
    expect(badge).toHaveTextContent(label);
  });

  it("renders tooltip content from error + message when failed", () => {
    render(
      <StatusBadge
        status="failed"
        failure={{ error: "ConnectError", message: "timeout" }}
      />,
    );
    expect(screen.getByTestId("status-badge")).toHaveAttribute(
      "title",
      "ConnectError: timeout",
    );
  });

  it("omits tooltip when failure is not provided on failed status", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByTestId("status-badge")).not.toHaveAttribute("title");
  });

  it("ignores failure prop when status is not failed", () => {
    render(
      <StatusBadge status="done" failure={{ error: "X", message: "y" }} />,
    );
    expect(screen.getByTestId("status-badge")).not.toHaveAttribute("title");
  });
});
