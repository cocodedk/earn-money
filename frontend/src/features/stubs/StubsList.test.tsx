import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { LocationProbe, withBareArray } from "../../test/helpers";
import { StubsList } from "./StubsList";
import { makeStub as stub } from "./__fixtures__/stub";

describe("StubsList", () => {
  it("shows a skeleton while loading", () => {
    withBareArray("/api/stubs/", []);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("shows an empty state when there are no stubs", async () => {
    withBareArray("/api/stubs/", []);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText("No stubs found.")).toBeInTheDocument();
  });

  it("renders rows with status badges and slug-as-link", async () => {
    withBareArray("/api/stubs/", [stub()]);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText("Framework detection")).toBeInTheDocument();
    expect(screen.getByText("framework-detection")).toBeInTheDocument();
    expect(screen.getByTestId("status-done")).toBeInTheDocument();
    const slugLink = screen.getByRole("link", { name: "1.1" });
    expect(slugLink).toHaveAttribute("href", "/stubs/1.1");
  });

  it("renders all four status badges with the right palette", async () => {
    withBareArray("/api/stubs/", [
      stub({ slug: "1.1", status: "done" }),
      stub({ slug: "1.2", status: "in-progress" }),
      stub({ slug: "1.3", status: "blocked" }),
      stub({ slug: "1.4", status: "pending" }),
    ]);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    await screen.findByTestId("status-done");
    expect(screen.getByTestId("status-done").className).toMatch(/bg-green/);
    expect(screen.getByTestId("status-in-progress").className).toMatch(/bg-blue/);
    expect(screen.getByTestId("status-blocked").className).toMatch(/bg-amber/);
    expect(screen.getByTestId("status-pending").className).toMatch(/bg-gray/);
  });

  it("renders an empty-string spec_slug as the em-dash placeholder", async () => {
    withBareArray("/api/stubs/", [stub({ spec_slug: "" })]);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText("—")).toBeInTheDocument();
  });

  it("shows a Backend-unreachable callout with Retry on fetch error", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.error()));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
    let calls = 0;
    server.use(
      msw.get("/api/stubs/", () => {
        calls += 1;
        return HttpResponse.json([]);
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(0));
  });

  it("navigates to the detail page when a slug link is clicked", async () => {
    withBareArray("/api/stubs/", [stub()]);
    renderWithProviders(
      <>
        <StubsList />
        <LocationProbe />
      </>,
      { route: "/stubs" },
    );
    await userEvent.click(await screen.findByRole("link", { name: "1.1" }));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/stubs/1.1"),
    );
  });
});
