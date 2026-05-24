---
tier: FAST
depends_on: []
files:
  creates: [frontend/src/features/missions/BudgetBars.test.tsx]
  modifies: [frontend/src/features/missions/MissionStrip.tsx, frontend/src/features/missions/MissionStrip.test.tsx]
allow_extra_files: false
---

# Task 5: BudgetBars — Test and Wire

**Goal:** Test the pre-built BudgetBars and replace the text budget in MissionStrip.

- [ ] **Step 1: Create BudgetBars.test.tsx**

```typescript
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
```

- [ ] **Step 2: Run tests** — `cd frontend && npx vitest run src/features/missions/BudgetBars.test.tsx` → PASS

- [ ] **Step 3: Replace text budget in MissionStrip.tsx**

Add import: `import { BudgetBars } from "./BudgetBars";`

Replace the `<span className={styles.budget}>` line with:

```tsx
<BudgetBars session={session} budgetOverlay={budgetOverlay} />
```

Remove the `budgetText` and `usedTurns` functions (no longer needed).

- [ ] **Step 4: Update MissionStrip.test.tsx**

Replace budget text assertions with BudgetBars-aware ones. The "8 of 25 turns used" tests should now check for "Turns: 8/25". The "5 turns used" fallback should stay the same (BudgetBars renders fallback text). Update test cases:

- `"8 of 25 turns used"` → `"Turns: 8/25"`
- `"5 turns used"` → stays `"5 turns used"` (fallback)
- `"0 of 25 turns used"` → `"Turns: 0/25"`
- `"7 of 25 turns used"` → `"Turns: 7/25"`

- [ ] **Step 5: Run MissionStrip tests** — `cd frontend && npx vitest run src/features/missions/MissionStrip.test.tsx` → PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/missions/BudgetBars.test.tsx frontend/src/features/missions/MissionStrip.tsx frontend/src/features/missions/MissionStrip.test.tsx
git commit -m "feat(frontend): budget mini-bars in MissionStrip — turns, HTTP, browser, LLM"
```
