---
tier: FAST
depends_on: []
files:
  creates: [frontend/src/features/missions/ObservationDetails.test.tsx]
  modifies: [frontend/src/features/missions/TurnCard.tsx]
allow_extra_files: false
---

# Task 3: ObservationDetails — Test and Wire

**Goal:** Test the pre-built ObservationDetails and replace the raw JSON dump in TurnCard's details panel.

- [ ] **Step 1: Create ObservationDetails.test.tsx**

```typescript
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
```

- [ ] **Step 2: Run tests** — `cd frontend && npx vitest run src/features/missions/ObservationDetails.test.tsx` → PASS

- [ ] **Step 3: Replace raw JSON in TurnCard with ObservationDetails**

In `TurnCard.tsx`, add import: `import { ObservationDetails } from "./ObservationDetails";`

Replace the observations `<details>` block inside the details panel (lines ~70-79) with:

```tsx
<ObservationDetails observations={action.observations} />
```

Keep the Action/Validation/Execution/Denied lines above it. Remove the old raw JSON `<details><summary>Observations...` block.

- [ ] **Step 4: Run tests** — `cd frontend && npx vitest run src/features/missions/TurnCard.test.tsx` → PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/ObservationDetails.test.tsx frontend/src/features/missions/TurnCard.tsx
git commit -m "feat(frontend): structured observation details — replace raw JSON in TurnCard"
```
