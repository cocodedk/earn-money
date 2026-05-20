import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageHeader } from "./PageHeader";

describe("PageHeader", () => {
  it("renders the title in an h1", () => {
    render(<PageHeader title="Projects" />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Projects" }),
    ).toBeInTheDocument();
  });

  it("renders an action slot when provided", () => {
    render(<PageHeader title="Projects" action={<button>New</button>} />);
    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
  });
});
