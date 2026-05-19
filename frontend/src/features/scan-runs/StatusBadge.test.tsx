import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("ScanRun StatusBadge", () => {
  it.each([
    ["queued", /bg-gray/],
    ["running", /bg-blue/],
    ["paused", /bg-yellow/],
    ["stopping", /bg-orange/],
    ["stopped", /bg-gray/],
    ["failed", /bg-red/],
    ["done", /bg-green/],
  ] as const)("renders the %s palette", (status, pattern) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByTestId(`status-${status}`).className).toMatch(pattern);
  });
});
