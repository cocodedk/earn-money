import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/renderWithProviders";
import { OutcomeDigest } from "./OutcomeDigest";
import { makeAction, makeObservation } from "./__fixtures__/mission";

describe("OutcomeDigest", () => {
  it("shows URL and title from page observation", () => {
    const action = makeAction({
      observations: [makeObservation({
        data: {
          identity: { url: "https://example.com/login", title: "Login" },
          discovered: { routes: ["/a"], assets: [] },
          elements: { links: 3, buttons: 1, forms: 1 },
          network: [{ url: "/api", status: 200, method: "GET" }],
        },
      })],
    });
    renderWithProviders(<OutcomeDigest action={action} />);
    expect(screen.getByTestId("outcome-digest")).toBeInTheDocument();
  });

  it("returns null for store_note actions", () => {
    const action = makeAction({ action_type: "store_note" });
    const { container } = renderWithProviders(<OutcomeDigest action={action} />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null when no observations", () => {
    const action = makeAction({ observations: [] });
    const { container } = renderWithProviders(<OutcomeDigest action={action} />);
    expect(container.innerHTML).toBe("");
  });
});
