# Task 6 — Tests: TurnCard

Test code for [Task 6](06-turn-card.md).

Create `frontend/src/features/missions/TurnCard.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/renderWithProviders";
import { TurnCard } from "./TurnCard";
import { makeTurn, makeAction } from "./__fixtures__/mission";

describe("TurnCard", () => {
  it("renders the plain-language title from describeTurn", () => {
    const turn = makeTurn({
      actions: [makeAction({ goal: "Look at the home page" })],
    });
    renderWithProviders(<TurnCard turn={turn} />);
    expect(screen.getByText("Look at the home page")).toBeInTheDocument();
  });

  it("shows a success icon for executed actions", () => {
    const turn = makeTurn({
      actions: [makeAction({ execution_status: "executed" })],
    });
    renderWithProviders(<TurnCard turn={turn} />);
    expect(screen.getByTestId("turn-icon-success")).toBeInTheDocument();
  });

  it("shows a denied icon for denied actions", () => {
    const turn = makeTurn({
      status: "action_denied",
      actions: [makeAction({
        validation_status: "denied_roe",
        execution_status: "skipped",
        denial_reason: "Not allowed",
      })],
    });
    renderWithProviders(<TurnCard turn={turn} />);
    expect(screen.getByTestId("turn-icon-denied")).toBeInTheDocument();
    expect(screen.getByText("Blocked: Not allowed")).toBeInTheDocument();
  });

  it("shows a running icon for in-progress turns", () => {
    const turn = makeTurn({
      status: "started",
      actions: [makeAction({ execution_status: "pending" })],
    });
    renderWithProviders(<TurnCard turn={turn} />);
    expect(screen.getByTestId("turn-icon-running")).toBeInTheDocument();
  });

  it("shows an error icon for failed actions", () => {
    const turn = makeTurn({
      status: "error",
      actions: [makeAction({ execution_status: "failed" })],
    });
    renderWithProviders(<TurnCard turn={turn} />);
    expect(screen.getByTestId("turn-icon-error")).toBeInTheDocument();
  });

  it("shows phase badge and turn index", () => {
    const turn = makeTurn({ index: 3, phase: "enumerate" });
    renderWithProviders(<TurnCard turn={turn} />);
    expect(screen.getByText("#3")).toBeInTheDocument();
    expect(screen.getByText("enumerate")).toBeInTheDocument();
  });

  it("hides technical details by default", () => {
    const turn = makeTurn();
    renderWithProviders(<TurnCard turn={turn} />);
    expect(screen.queryByText(/Action:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Tokens:/)).not.toBeInTheDocument();
  });

  it("omits details control when no actions exist yet", () => {
    const turn = makeTurn({ actions: [] });
    renderWithProviders(<TurnCard turn={turn} />);
    expect(screen.queryByRole("button", { name: /details/i })).not.toBeInTheDocument();
  });

  it("shows details when expanded", async () => {
    const user = userEvent.setup();
    const turn = makeTurn({ input_tokens: 1200, output_tokens: 350 });
    renderWithProviders(<TurnCard turn={turn} />);
    await user.click(screen.getByRole("button", { name: /details/i }));
    expect(screen.getByText(/1200/)).toBeInTheDocument();
    expect(screen.getByText(/350/)).toBeInTheDocument();
  });

  it("details button has accessible expanded state", async () => {
    const user = userEvent.setup();
    const turn = makeTurn();
    renderWithProviders(<TurnCard turn={turn} />);
    const btn = screen.getByRole("button", { name: /details/i });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    await user.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });

  it("status icon has aria-label", () => {
    const turn = makeTurn({
      actions: [makeAction({ execution_status: "executed" })],
    });
    renderWithProviders(<TurnCard turn={turn} />);
    const icon = screen.getByTestId("turn-icon-success");
    expect(icon).toHaveAttribute("aria-label", "Completed");
  });
});
```
