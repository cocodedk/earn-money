---
tier: FAST
depends_on: []
files:
  modifies: [frontend/src/features/missions/TurnCard.tsx, frontend/src/features/missions/TurnCard.test.tsx, frontend/src/features/missions/TurnCard.module.css]
allow_extra_files: false
---

# Task 1: Intent Lines in TurnCard

**Goal:** Always show `reason` and `hypothesis` below the goal line.

- [ ] **Step 1: Add failing tests to TurnCard.test.tsx**

Add these tests inside the existing `describe("TurnCard")`:

```typescript
it("shows reason when non-empty", () => {
  const turn = makeTurn({
    actions: [makeAction({ reason: "Need to understand page structure" })],
  });
  renderWithProviders(<TurnCard turn={turn} />);
  expect(screen.getByText(/Need to understand page structure/)).toBeInTheDocument();
});

it("shows hypothesis when non-empty", () => {
  const turn = makeTurn({
    actions: [makeAction({ hypothesis: "Page may contain hidden links" })],
  });
  renderWithProviders(<TurnCard turn={turn} />);
  expect(screen.getByText(/Page may contain hidden links/)).toBeInTheDocument();
});

it("hides reason line when empty", () => {
  const turn = makeTurn({
    actions: [makeAction({ reason: "" })],
  });
  renderWithProviders(<TurnCard turn={turn} />);
  expect(screen.queryByText("Why:")).not.toBeInTheDocument();
});

it("hides hypothesis line when empty", () => {
  const turn = makeTurn({
    actions: [makeAction({ hypothesis: "" })],
  });
  renderWithProviders(<TurnCard turn={turn} />);
  expect(screen.queryByText("Expected:")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/TurnCard.test.tsx`

- [ ] **Step 3: Add intent lines to TurnCard.tsx**

After the `{desc.result && ...}` line (~line 49), add:

```tsx
{action && action.reason && (
  <p className={styles.intent}>
    <span className={styles.intentLabel}>Why:</span> {action.reason}
  </p>
)}
{action && action.hypothesis && (
  <p className={styles.intent}>
    <span className={styles.intentLabel}>Expected:</span> {action.hypothesis}
  </p>
)}
```

Where `action` is `actions[0]` — already available as the first action.
Add `const action = actions[0] ?? null;` after `const actions = turn.actions;`.

- [ ] **Step 4: Add CSS for intent lines to TurnCard.module.css**

```css
.intent {
  font-size: var(--text-code);
  color: var(--ink-muted);
  margin-top: 0.125rem;
  line-height: 1.4;
}
.intentLabel {
  font-weight: 600;
  color: var(--ink-soft);
}
```

- [ ] **Step 5: Run tests** — `cd frontend && npx vitest run src/features/missions/TurnCard.test.tsx` → PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/missions/TurnCard.tsx frontend/src/features/missions/TurnCard.test.tsx frontend/src/features/missions/TurnCard.module.css
git commit -m "feat(frontend): TurnCard intent lines — reason + hypothesis always visible"
```
