import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Callout } from "./Callout";

describe("Callout", () => {
  it("renders children with the variant data attr", () => {
    render(<Callout variant="error">Boom</Callout>);
    const el = screen.getByTestId("callout");
    expect(el).toHaveAttribute("data-variant", "error");
    expect(el).toHaveTextContent("Boom");
  });

  it("renders title and action button", async () => {
    const onClick = vi.fn();
    render(
      <Callout
        variant="warning"
        title="Heads up"
        action={{ label: "Retry", onClick }}
      >
        body text
      </Callout>,
    );
    expect(screen.getByText("Heads up")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("omits the action button when no action is provided", () => {
    render(<Callout variant="info">just text</Callout>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
