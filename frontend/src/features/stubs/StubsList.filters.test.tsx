import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { StubsList } from "./StubsList";
import { makeStub } from "./__fixtures__/stub";

function withStubs() {
  server.use(
    msw.get("/api/stubs/", () =>
      HttpResponse.json([
        makeStub({ slug: "1.1", phase: 1, status: "done", category: "info" }),
        makeStub({ slug: "1.2", phase: 1, status: "pending", category: "info" }),
        makeStub({ slug: "2.1", phase: 2, status: "done", category: "auth" }),
      ]),
    ),
  );
}

describe("StubsList filters", () => {
  it("renders the filter bar with phase, status, category selects", async () => {
    withStubs();
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByTestId("stubs-filters-bar")).toBeInTheDocument();
    expect(screen.getByTestId("filter-phase")).toBeInTheDocument();
    expect(screen.getByTestId("filter-status")).toBeInTheDocument();
    expect(screen.getByTestId("filter-category")).toBeInTheDocument();
  });

  it("filters by phase via URL search param", async () => {
    withStubs();
    renderWithProviders(<StubsList />, { route: "/stubs?phase=2" });
    expect(await screen.findByText("2.1")).toBeInTheDocument();
    expect(screen.queryByText("1.1")).not.toBeInTheDocument();
    expect(screen.queryByText("1.2")).not.toBeInTheDocument();
  });

  it("filters by status", async () => {
    withStubs();
    renderWithProviders(<StubsList />, { route: "/stubs?status=pending" });
    expect(await screen.findByText("1.2")).toBeInTheDocument();
    expect(screen.queryByText("1.1")).not.toBeInTheDocument();
    expect(screen.queryByText("2.1")).not.toBeInTheDocument();
  });

  it("filters by category", async () => {
    withStubs();
    renderWithProviders(<StubsList />, { route: "/stubs?category=auth" });
    expect(await screen.findByText("2.1")).toBeInTheDocument();
    expect(screen.queryByText("1.1")).not.toBeInTheDocument();
  });

  it("AND-combines multiple filters", async () => {
    withStubs();
    renderWithProviders(<StubsList />, {
      route: "/stubs?phase=1&status=done",
    });
    expect(await screen.findByText("1.1")).toBeInTheDocument();
    expect(screen.queryByText("1.2")).not.toBeInTheDocument();
    expect(screen.queryByText("2.1")).not.toBeInTheDocument();
  });

  it("shows empty-state-with-filters when no stubs match", async () => {
    withStubs();
    renderWithProviders(<StubsList />, { route: "/stubs?phase=99" });
    expect(
      await screen.findByText(/No stubs match the current filters/i),
    ).toBeInTheDocument();
  });

  it("selecting a filter updates the URL search params", async () => {
    withStubs();
    renderWithProviders(<StubsList />, { route: "/stubs" });
    await screen.findByText("1.1");
    await userEvent.selectOptions(screen.getByTestId("filter-status"), "done");
    expect(screen.queryByText("1.2")).not.toBeInTheDocument();
    expect(screen.getByText("1.1")).toBeInTheDocument();
    expect(screen.getByText("2.1")).toBeInTheDocument();
  });

  it("clearing a filter (back to 'All') shows all rows again", async () => {
    withStubs();
    renderWithProviders(<StubsList />, { route: "/stubs?status=done" });
    await screen.findByText("1.1");
    expect(screen.queryByText("1.2")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByTestId("filter-status"), "");
    expect(await screen.findByText("1.2")).toBeInTheDocument();
  });
});
