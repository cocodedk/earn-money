import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComingSoon } from "./ComingSoon";

describe("ComingSoon", () => {
  it("renders the page name and the not-built-yet message", () => {
    render(<ComingSoon name="Targets" />);
    expect(screen.getByRole("heading", { name: "Targets" })).toBeInTheDocument();
    expect(screen.getByText(/not built yet/i)).toBeInTheDocument();
  });
});
