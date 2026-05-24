import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ObservationDetails } from "./ObservationDetails";
import { makeObservation } from "./__fixtures__/mission";

describe("ObservationDetails", () => {
  it("shows page URL and title", () => {
    renderWithProviders(
      <ObservationDetails observations={[makeObservation({
        data: {
          url: "https://example.com",
          title: "Home",
          discovered: { routes: [], assets: [] },
          elements: {},
          network: [],
        },
      })]} />,
    );
    expect(screen.getByText("https://example.com")).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
  });

  it("shows routes list", () => {
    renderWithProviders(
      <ObservationDetails observations={[makeObservation({
        data: {
          discovered: { routes: ["/login", "/admin"], assets: [] },
          network: [],
        },
      })]} />,
    );
    expect(screen.getByText("/login")).toBeInTheDocument();
    expect(screen.getByText("/admin")).toBeInTheDocument();
  });

  it("shows network table", () => {
    renderWithProviders(
      <ObservationDetails observations={[makeObservation({
        data: {
          discovered: { routes: [], assets: [] },
          network: [{ url: "/api/health", status: 200, method: "GET" }],
        },
      })]} />,
    );
    expect(screen.getByText("/api/health")).toBeInTheDocument();
  });

  it("returns null for empty observations", () => {
    const { container } = renderWithProviders(
      <ObservationDetails observations={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("has a Raw JSON disclosure", () => {
    renderWithProviders(
      <ObservationDetails observations={[makeObservation()]} />,
    );
    expect(screen.getByText("Raw JSON")).toBeInTheDocument();
  });
});
