import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { UseQueryResult } from "@tanstack/react-query";
import { ListPageGuard } from "./ListPageGuard";

type GuardQuery = Pick<UseQueryResult, "isError" | "refetch">;

function asQuery(overrides: Partial<GuardQuery> = {}): GuardQuery {
  return {
    isError: false,
    refetch: vi.fn().mockResolvedValue({}),
    ...overrides,
  } as GuardQuery;
}

describe("ListPageGuard", () => {
  it("renders the children on the happy path", () => {
    render(
      <ListPageGuard query={asQuery()} errorBody="boom">
        <span data-testid="rows">rows</span>
      </ListPageGuard>,
    );
    expect(screen.getByTestId("rows")).toBeInTheDocument();
    expect(screen.queryByText(/backend unreachable/i)).not.toBeInTheDocument();
  });

  it("renders the BackendUnreachableCallout with the supplied body on error", () => {
    render(
      <ListPageGuard
        query={asQuery({ isError: true })}
        errorBody="Could not load widgets."
      >
        <span data-testid="rows">rows</span>
      </ListPageGuard>,
    );
    expect(screen.getByText(/backend unreachable/i)).toBeInTheDocument();
    expect(screen.getByText("Could not load widgets.")).toBeInTheDocument();
    expect(screen.queryByTestId("rows")).not.toBeInTheDocument();
  });

  it("fires query.refetch when the Retry button is clicked", async () => {
    const refetch = vi.fn().mockResolvedValue({});
    render(
      <ListPageGuard
        query={asQuery({ isError: true, refetch: refetch as never })}
        errorBody="boom"
      >
        <span>rows</span>
      </ListPageGuard>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
