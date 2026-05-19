import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["done", /bg-green/],
    ["in-progress", /bg-blue/],
    ["blocked", /bg-amber/],
    ["pending", /bg-gray/],
  ] as const)("renders the %s palette", (status, pattern) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByTestId(`status-${status}`).className).toMatch(pattern);
  });
});
