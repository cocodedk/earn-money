import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/renderWithProviders";
import { MissionStrip } from "./MissionStrip";
import { makeSession } from "./__fixtures__/mission";
import type { BudgetSnapshot } from "./types";

describe("MissionStrip", () => {
  it("shows mission profile and target host", () => {
    const session = makeSession({
      mission_profile: "juice_shop_scoreboard",
      target_host: "target.cocode.dk",
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("juice_shop_scoreboard")).toBeInTheDocument();
    expect(screen.getByText("target.cocode.dk")).toBeInTheDocument();
  });

  it("shows session status pill", () => {
    const session = makeSession({ status: "running" });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("renders phase chips with current highlighted", () => {
    const session = makeSession({
      active_phases: ["recon", "enumerate", "report"],
      current_phase: "enumerate",
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("recon")).toBeInTheDocument();
    expect(screen.getByText("enumerate")).toBeInTheDocument();
    expect(screen.getByText("report")).toBeInTheDocument();
    const current = screen.getByTestId("phase-chip-enumerate");
    expect(current).toHaveAttribute("data-current", "true");
    expect(current).toHaveAttribute("aria-current", "step");
  });

  it("shows 'N of M turns used' when max_turns present", () => {
    const session = makeSession({
      mission_budget: { max_turns: 25 },
      consumed_budget: { turns: 8, mission: { turns: 8 } },
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("8 of 25 turns used")).toBeInTheDocument();
  });

  it("degrades to 'N turns used' when max_turns absent", () => {
    const session = makeSession({
      mission_budget: {},
      consumed_budget: { turns: 5, mission: { turns: 5 } },
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("5 turns used")).toBeInTheDocument();
  });

  it("shows 0 when consumed_budget has no turns", () => {
    const session = makeSession({
      mission_budget: { max_turns: 25 },
      consumed_budget: {},
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("0 of 25 turns used")).toBeInTheDocument();
  });

  it("uses budgetOverlay when provided", () => {
    const session = makeSession({
      mission_budget: { max_turns: 25 },
      consumed_budget: { turns: 3, mission: { turns: 3 } },
    });
    const overlay: BudgetSnapshot = { turns: 7, mission: { turns: 7 } };
    renderWithProviders(<MissionStrip session={session} budgetOverlay={overlay} />);
    expect(screen.getByText("7 of 25 turns used")).toBeInTheDocument();
  });

  it("shows terminal reason when present", () => {
    const session = makeSession({
      status: "failed",
      terminal_reason: "Budget exhausted",
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("Budget exhausted")).toBeInTheDocument();
  });

  it("shows generic copy when terminal with no reason", () => {
    const session = makeSession({
      status: "stopped",
      terminal_reason: null,
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("stopped")).toBeInTheDocument();
    expect(screen.getByText("Mission ended.")).toBeInTheDocument();
  });
});
