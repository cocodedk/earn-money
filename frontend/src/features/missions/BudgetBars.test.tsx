import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/renderWithProviders";
import { BudgetBars } from "./BudgetBars";
import { makeSession } from "./__fixtures__/mission";

describe("BudgetBars", () => {
  it("renders bars for budget dimensions with max values", () => {
    const session = makeSession({
      mission_budget: { max_turns: 25, max_http_requests: 60 },
      consumed_budget: { turns: 8, mission: { turns: 8, http_requests: 15 } },
    });
    renderWithProviders(<BudgetBars session={session} budgetOverlay={null} />);
    expect(screen.getByTestId("budget-bars")).toBeInTheDocument();
    expect(screen.getByText(/Turns: 8\/25/)).toBeInTheDocument();
    expect(screen.getByText(/HTTP: 15\/60/)).toBeInTheDocument();
  });

  it("hides bars for dimensions without max", () => {
    const session = makeSession({
      mission_budget: { max_turns: 25 },
      consumed_budget: { turns: 5, mission: { turns: 5 } },
    });
    renderWithProviders(<BudgetBars session={session} budgetOverlay={null} />);
    expect(screen.getByText(/Turns: 5\/25/)).toBeInTheDocument();
    expect(screen.queryByText(/HTTP/)).not.toBeInTheDocument();
  });

  it("falls back to text when no max values defined", () => {
    const session = makeSession({
      mission_budget: {},
      consumed_budget: { turns: 3, mission: { turns: 3 } },
    });
    renderWithProviders(<BudgetBars session={session} budgetOverlay={null} />);
    expect(screen.getByText("3 turns used")).toBeInTheDocument();
    expect(screen.queryByTestId("budget-bars")).not.toBeInTheDocument();
  });

  it("uses budget overlay when provided", () => {
    const session = makeSession({
      mission_budget: { max_turns: 25 },
      consumed_budget: { turns: 3, mission: { turns: 3 } },
    });
    renderWithProviders(
      <BudgetBars session={session} budgetOverlay={{ turns: 10, mission: { turns: 10 } }} />,
    );
    expect(screen.getByText(/Turns: 10\/25/)).toBeInTheDocument();
  });
});
