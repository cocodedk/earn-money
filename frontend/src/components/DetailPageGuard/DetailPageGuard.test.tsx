import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";
import { DetailPageGuard, type DetailPageGuardOptions } from "./DetailPageGuard";
import { HttpError } from "../../lib/http";

const OPTIONS: DetailPageGuardOptions = {
  notFoundTitle: "Widget not found",
  notFoundMessage: 'No widget matches "w-9".',
  backTo: "/widgets",
  backLabel: "Back to widgets.",
  errorTitle: "Widget",
  errorBody: "Could not load widget.",
};

function asQuery(overrides: Partial<UseQueryResult<{ id: string }>>) {
  return {
    data: undefined,
    isError: false,
    isLoading: false,
    error: null,
    ...overrides,
  } as UseQueryResult<{ id: string }>;
}

function renderGuard(
  query: UseQueryResult<{ id: string }>,
  options: DetailPageGuardOptions = OPTIONS,
) {
  return render(
    <MemoryRouter>
      <DetailPageGuard query={query} options={options}>
        {(data) => <span data-testid="data">{data.id}</span>}
      </DetailPageGuard>
    </MemoryRouter>,
  );
}

describe("DetailPageGuard", () => {
  it("renders the not-found callout with back-link on 404", () => {
    renderGuard(
      asQuery({
        isError: true,
        error: new HttpError(new Response("", { status: 404 })),
      }),
    );
    expect(screen.getByText("Widget not found")).toBeInTheDocument();
    expect(screen.getByText(/no widget matches "w-9"/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /back to widgets/i }),
    ).toHaveAttribute("href", "/widgets");
  });

  it("renders the BackendUnreachableCallout on non-404 errors", () => {
    renderGuard(
      asQuery({
        isError: true,
        error: new HttpError(new Response("", { status: 500 })),
      }),
    );
    expect(screen.getByText(/backend unreachable/i)).toBeInTheDocument();
    expect(screen.getByText("Could not load widget.")).toBeInTheDocument();
  });

  it("renders Loading… by default when data is undefined and not errored", () => {
    renderGuard(asQuery({}));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders a custom loading title when provided", () => {
    renderGuard(asQuery({}), {
      ...OPTIONS,
      loadingTitle: "Fetching widget…",
    });
    expect(screen.getByText("Fetching widget…")).toBeInTheDocument();
  });

  it("renders the children function with data on the happy path", () => {
    renderGuard(asQuery({ data: { id: "w-1" } }));
    expect(screen.getByTestId("data").textContent).toBe("w-1");
  });

  it("renders children when isError=true but data is present (background error with stale data)", () => {
    renderGuard(
      asQuery({
        data: { id: "w-cached" },
        isError: true,
        error: new HttpError(new Response("", { status: 500 })),
      }),
    );
    expect(screen.getByTestId("data")).toBeInTheDocument();
    expect(screen.getByTestId("data").textContent).toBe("w-cached");
    expect(screen.queryByText(/backend unreachable/i)).not.toBeInTheDocument();
  });

  it("renders children when 404 but data is present (background 404 with stale data)", () => {
    renderGuard(
      asQuery({
        data: { id: "w-cached" },
        isError: true,
        error: new HttpError(new Response("", { status: 404 })),
      }),
    );
    expect(screen.getByTestId("data")).toBeInTheDocument();
    expect(screen.getByTestId("data").textContent).toBe("w-cached");
    expect(screen.queryByText("Widget not found")).not.toBeInTheDocument();
  });
});
