import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders the message", () => {
    render(<EmptyState message="No projects yet." />);
    expect(screen.getByText("No projects yet.")).toBeInTheDocument();
  });

  it("renders and fires the action button when provided", async () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        message="No projects yet."
        action={{ label: "Create project", onClick }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
