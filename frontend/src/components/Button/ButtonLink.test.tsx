import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ButtonLink } from "./ButtonLink";

function renderInRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("ButtonLink", () => {
  it("renders an anchor with the given href and primary variant by default", () => {
    renderInRouter(<ButtonLink to="/projects/new">Create project</ButtonLink>);
    const link = screen.getByRole("link", { name: "Create project" });
    expect(link).toHaveAttribute("href", "/projects/new");
    expect(link).toHaveAttribute("data-variant", "primary");
  });

  it("supports the danger variant", () => {
    renderInRouter(
      <ButtonLink to="/projects/new" variant="danger">
        Delete
      </ButtonLink>,
    );
    expect(screen.getByRole("link")).toHaveAttribute("data-variant", "danger");
  });

  it("supports the secondary variant", () => {
    renderInRouter(
      <ButtonLink to="/projects/new" variant="secondary">
        Cancel
      </ButtonLink>,
    );
    expect(screen.getByRole("link")).toHaveAttribute(
      "data-variant",
      "secondary",
    );
  });
});
