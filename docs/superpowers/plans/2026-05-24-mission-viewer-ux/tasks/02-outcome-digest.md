---
tier: FAST
depends_on: []
files:
  creates: [frontend/src/features/missions/OutcomeDigest.test.tsx]
  modifies: [frontend/src/features/missions/TurnCard.tsx]
allow_extra_files: false
---

# Task 2: OutcomeDigest — Test and Wire

**Goal:** Test the pre-built OutcomeDigest component and wire it into TurnCard.

- [ ] **Step 1: Create OutcomeDigest.test.tsx**

```typescript
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
```

- [ ] **Step 2: Run tests** — `cd frontend && npx vitest run src/features/missions/OutcomeDigest.test.tsx` → PASS

- [ ] **Step 3: Wire OutcomeDigest into TurnCard.tsx**

Add import at top: `import { OutcomeDigest } from "./OutcomeDigest";`

After the intent lines (reason/hypothesis), add:

```tsx
{action && <OutcomeDigest action={action} />}
```

- [ ] **Step 4: Run TurnCard tests** — `cd frontend && npx vitest run src/features/missions/TurnCard.test.tsx` → PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/OutcomeDigest.test.tsx frontend/src/features/missions/TurnCard.tsx
git commit -m "feat(frontend): wire OutcomeDigest into TurnCard — URL, title, counters"
```
