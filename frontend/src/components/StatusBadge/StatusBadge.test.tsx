import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

const PALETTE = {
  ok: "bg-green-100 text-green-800",
  warn: "bg-amber-100 text-amber-800",
  fail: "bg-red-100 text-red-800",
} as const;

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="ok" palette={PALETTE} />);
    expect(screen.getByTestId("status-ok").textContent).toBe("ok");
  });

  it("applies the palette class for the given status", () => {
    render(<StatusBadge status="warn" palette={PALETTE} />);
    expect(screen.getByTestId("status-warn").className).toMatch(/bg-amber/);
  });

  it("encodes status into the data-testid attribute", () => {
    render(<StatusBadge status="fail" palette={PALETTE} />);
    expect(screen.getByTestId("status-fail")).toBeInTheDocument();
  });
});
