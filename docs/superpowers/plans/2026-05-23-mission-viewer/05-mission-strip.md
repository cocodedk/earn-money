# Mission Viewer Plan — Task 5: MissionStrip Component

**Goal:** Sticky top strip showing mission name, status pill, phase chips, and budget counter.

---

### Task 7: MissionStrip

**Files:**
- Create: `frontend/src/features/missions/MissionStrip.tsx`
- Create: `frontend/src/features/missions/MissionStrip.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/features/missions/MissionStrip.test.tsx`:

```typescript
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

  it("renders phase chips from active_phases with current highlighted", () => {
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
  });

  it("shows budget as 'N of M turns used' when max_turns present", () => {
    const session = makeSession({
      mission_budget: { max_turns: 25 },
      consumed_budget: { turns: 8, mission: { turns: 8 } },
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("8 of 25 turns used")).toBeInTheDocument();
  });

  it("degrades to 'N turns used' when max_turns is absent", () => {
    const session = makeSession({
      mission_budget: {},
      consumed_budget: { turns: 5, mission: { turns: 5 } },
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("5 turns used")).toBeInTheDocument();
  });

  it("shows 0 turns used when consumed_budget has no turns", () => {
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

  it("shows terminal status and reason", () => {
    const session = makeSession({
      status: "failed",
      terminal_reason: "Budget exhausted",
    });
    renderWithProviders(<MissionStrip session={session} budgetOverlay={null} />);
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("Budget exhausted")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/MissionStrip.test.tsx`
Expected: FAIL — `MissionStrip` not found.

- [ ] **Step 3: Implement MissionStrip**

Create `frontend/src/features/missions/MissionStrip.tsx`:

```tsx
import type { AgentSession, BudgetSnapshot } from "./types";
import { isTerminalStatus } from "./types";

type Props = {
  session: AgentSession;
  budgetOverlay: BudgetSnapshot | null;
};

function usedTurns(budget: BudgetSnapshot): number {
  return budget.mission?.turns ?? budget.turns ?? 0;
}

function budgetText(session: AgentSession, overlay: BudgetSnapshot | null): string {
  const snap = overlay ?? session.consumed_budget;
  const used = usedTurns(snap);
  const max = session.mission_budget.max_turns;
  return max != null ? `${used} of ${max} turns used` : `${used} turns used`;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-200 text-gray-700",
  running: "bg-blue-100 text-blue-700",
  paused: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  stopped: "bg-gray-200 text-gray-700",
};

export function MissionStrip({ session, budgetOverlay }: Props) {
  const isTerminal = isTerminalStatus(session.status);

  return (
    <div className="sticky top-0 z-10 bg-white border-b px-4 py-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-semibold truncate">{session.mission_profile}</span>
          <span className="text-sm text-gray-500 truncate">{session.target_host}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[session.status] ?? ""}`}>
            {session.status}
          </span>
        </div>

        <div className="flex items-center gap-1" role="list" aria-label="Mission phases">
          {session.active_phases.map((phase, i) => (
            <span key={phase} role="listitem">
              {i > 0 && <span className="text-gray-300 mr-1" aria-hidden="true">→</span>}
              <span
                data-testid={`phase-chip-${phase}`}
                data-current={phase === session.current_phase ? "true" : "false"}
                className={`text-xs px-1.5 py-0.5 rounded ${
                  phase === session.current_phase
                    ? "bg-blue-600 text-white font-medium"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {phase}
              </span>
            </span>
          ))}
        </div>

        <span className="text-sm text-gray-600 ml-auto">
          {budgetText(session, budgetOverlay)}
        </span>
      </div>

      {isTerminal && session.terminal_reason && (
        <p className="text-sm text-gray-600 mt-1">{session.terminal_reason}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/features/missions/MissionStrip.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/MissionStrip.tsx frontend/src/features/missions/MissionStrip.test.tsx
git commit -m "feat(frontend): MissionStrip — sticky header with phases and budget"
```
