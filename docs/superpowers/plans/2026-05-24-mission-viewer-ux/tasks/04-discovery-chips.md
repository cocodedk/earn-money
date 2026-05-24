---
tier: FAST
depends_on: []
files:
  creates: [frontend/src/features/missions/DiscoveryChips.test.tsx]
  modifies: [frontend/src/features/missions/StoryTimeline.tsx]
allow_extra_files: false
---

# Task 4: DiscoveryChips — Test and Wire

**Goal:** Test the pre-built DiscoveryChips and wire into StoryTimeline below each turn.

- [ ] **Step 1: Create DiscoveryChips.test.tsx**

```typescript
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/renderWithProviders";
import { DiscoveryChips } from "./DiscoveryChips";
import { makeTurn, makeNote, makeAction, makeObservation } from "./__fixtures__/mission";

describe("DiscoveryChips", () => {
  it("renders chips from route notes", () => {
    const turn = makeTurn();
    const notes = [
      makeNote({ note_type: "route", content: { text: "/login" } }),
      makeNote({ note_type: "route", content: { text: "/admin" }, id: "n-2" }),
    ];
    renderWithProviders(<DiscoveryChips turn={turn} notes={notes} />);
    expect(screen.getByText("/login")).toBeInTheDocument();
    expect(screen.getByText("/admin")).toBeInTheDocument();
  });

  it("caps at 3 and shows +N more", () => {
    const turn = makeTurn({
      actions: [makeAction({
        observations: [makeObservation({
          data: {
            discovered: { routes: ["/a", "/b", "/c", "/d", "/e"], assets: [] },
          },
        })],
      })],
    });
    renderWithProviders(<DiscoveryChips turn={turn} notes={[]} />);
    expect(screen.getByTestId("chips-expand")).toHaveTextContent("+2 more");
  });

  it("expands on click", async () => {
    const user = userEvent.setup();
    const turn = makeTurn({
      actions: [makeAction({
        observations: [makeObservation({
          data: { discovered: { routes: ["/a", "/b", "/c", "/d"], assets: [] } },
        })],
      })],
    });
    renderWithProviders(<DiscoveryChips turn={turn} notes={[]} />);
    await user.click(screen.getByTestId("chips-expand"));
    expect(screen.getByText("/d")).toBeInTheDocument();
    expect(screen.queryByTestId("chips-expand")).not.toBeInTheDocument();
  });

  it("returns null when no chips", () => {
    const turn = makeTurn({ actions: [makeAction({ observations: [] })] });
    const { container } = renderWithProviders(
      <DiscoveryChips turn={turn} notes={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });
});
```

- [ ] **Step 2: Run tests** — `cd frontend && npx vitest run src/features/missions/DiscoveryChips.test.tsx` → PASS

- [ ] **Step 3: Wire DiscoveryChips into StoryTimeline.tsx**

Add import: `import { DiscoveryChips } from "./DiscoveryChips";`

Inside the turn map, after `<TurnCard turn={turn} />` and before the notes block, add:

```tsx
<DiscoveryChips turn={turn} notes={turnNotes} />
```

- [ ] **Step 4: Run StoryTimeline tests** — `cd frontend && npx vitest run src/features/missions/StoryTimeline.test.tsx` → PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/DiscoveryChips.test.tsx frontend/src/features/missions/StoryTimeline.tsx
git commit -m "feat(frontend): discovery chips below turns — routes, assets, candidates"
```
