# Mission Viewer Plan — Task 4: TurnCard Component

**Goal:** Render a single turn as a card with status icon, plain-language text, phase badge, timestamp, and collapsible Details.

---

### Task 6: TurnCard

**Files:**
- Create: `frontend/src/features/missions/TurnCard.tsx`
- Create: `frontend/src/features/missions/TurnCard.test.tsx`

- [ ] **Step 1: Write failing tests**

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
    expect(screen.queryByText(/input_tokens/)).not.toBeInTheDocument();
  });

  it("shows technical details when Details is expanded", async () => {
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
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/TurnCard.test.tsx`
Expected: FAIL — `TurnCard` not found.

- [ ] **Step 3: Implement TurnCard**

Create `frontend/src/features/missions/TurnCard.tsx`:

```tsx
import { useState } from "react";
import type { AgentTurn } from "./types";
import { describeTurn } from "./describeTurn";

const TONE_ICON: Record<string, { testId: string; label: string; cls: string }> = {
  success: { testId: "turn-icon-success", label: "Completed", cls: "text-green-600" },
  denied:  { testId: "turn-icon-denied",  label: "Blocked",   cls: "text-yellow-600" },
  error:   { testId: "turn-icon-error",   label: "Failed",    cls: "text-red-600" },
  running: { testId: "turn-icon-running", label: "Running",   cls: "text-blue-500" },
  neutral: { testId: "turn-icon-neutral", label: "Done",      cls: "text-gray-500" },
};

function StatusIcon({ tone }: { tone: string }) {
  const cfg = TONE_ICON[tone] ?? TONE_ICON.neutral;
  return (
    <span
      data-testid={cfg.testId}
      aria-label={cfg.label}
      className={cfg.cls}
    >
      {tone === "success" && "✓"}
      {tone === "denied" && "⚠"}
      {tone === "error" && "✗"}
      {tone === "running" && "●"}
      {tone === "neutral" && "•"}
    </span>
  );
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

export function TurnCard({ turn }: { turn: AgentTurn }) {
  const [open, setOpen] = useState(false);
  const desc = describeTurn(turn);
  const action = turn.actions[0];

  return (
    <div data-testid={`turn-card-${turn.index}`} className="py-2 border-b">
      <div className="flex items-start gap-2">
        <StatusIcon tone={desc.tone} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-gray-500">#{turn.index}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100">{turn.phase}</span>
            <span className="text-xs text-gray-400" title={turn.created_at}>
              {relativeTime(turn.created_at)}
            </span>
          </div>
          <p className="mt-0.5">{desc.title}</p>
          {desc.result && <p className="text-sm text-gray-600 mt-0.5">{desc.result}</p>}
        </div>
      </div>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="text-xs text-gray-500 mt-1 underline"
      >
        Details
      </button>
      {open && action && (
        <div className="mt-1 text-xs text-gray-500 bg-gray-50 p-2 rounded font-mono">
          <div>Action: {action.action_type}</div>
          <div>Validation: {action.validation_status}</div>
          <div>Execution: {action.execution_status}</div>
          <div>Tokens: {turn.input_tokens} in / {turn.output_tokens} out</div>
          <div>Time: {turn.created_at}</div>
          {action.observations.length > 0 && (
            <details className="mt-1">
              <summary>Observations ({action.observations.length})</summary>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap">
                {JSON.stringify(action.observations.map((o) => ({
                  type: o.observation_type,
                  data: o.data,
                })), null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/features/missions/TurnCard.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/TurnCard.tsx frontend/src/features/missions/TurnCard.test.tsx
git commit -m "feat(frontend): TurnCard — status icon, plain text, collapsible details"
```
