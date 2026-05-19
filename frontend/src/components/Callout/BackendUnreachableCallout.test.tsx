import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BackendUnreachableCallout } from "./BackendUnreachableCallout";
import { BACKEND_UNREACHABLE } from "../../lib/applyParsedError";

describe("BackendUnreachableCallout", () => {
  it("renders the shared title and body children", () => {
    render(<BackendUnreachableCallout>Boom.</BackendUnreachableCallout>);
    expect(screen.getByText(BACKEND_UNREACHABLE)).toBeInTheDocument();
    expect(screen.getByText("Boom.")).toBeInTheDocument();
  });

  it("renders a Retry button that fires onRetry when provided", async () => {
    const onRetry = vi.fn();
    render(
      <BackendUnreachableCallout onRetry={onRetry}>
        Boom.
      </BackendUnreachableCallout>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("omits the Retry button when onRetry is not provided", () => {
    render(<BackendUnreachableCallout>Boom.</BackendUnreachableCallout>);
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
  });
});
