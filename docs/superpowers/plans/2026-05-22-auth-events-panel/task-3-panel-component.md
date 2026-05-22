# Task 3 — `TargetAuthEventsPanel` component

**Goal:** A section that loads auth events for a target via the Task 1 hook and renders one `AuthEventPill` (Task 2) per event in newest-first order. Renders nothing when `count === 0`. Shows a "+N more in the full events feed below." hint when the result is paginated and there are unshown events.

**Files:**
- Create: `frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.tsx`
- Create: `frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.module.css`
- Test: `frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx`

## Steps

- [ ] **Step 1: Write the failing empty-state test**

```tsx
// TargetAuthEventsPanel.test.tsx
import { describe, it, expect } from "vitest";
import { http as msw, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { TargetAuthEventsPanel } from "./TargetAuthEventsPanel";
import { makeEvent } from "../../scan-runs/__fixtures__/event";

const TARGET_ID = "22222222-2222-2222-2222-222222222222";

function authPage(
  rows: ReturnType<typeof makeEvent>[],
  next: string | null = null,
) {
  // backend returns oldest-first; the hook reverses for the component,
  // so feed tests the same oldest-first ordering the API returns.
  return { count: rows.length, next, previous: null, results: rows };
}

describe("TargetAuthEventsPanel", () => {
  it("renders nothing when count is 0", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/events/", () => {
        calls += 1;
        return HttpResponse.json(authPage([]));
      }),
    );
    const { container } = renderWithProviders(
      <TargetAuthEventsPanel targetId={TARGET_ID} />,
    );
    await waitFor(() => expect(calls).toBe(1));
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx
```
Expected: FAIL — `TargetAuthEventsPanel` not defined.

- [ ] **Step 3: Write the minimal panel + CSS**

```tsx
// TargetAuthEventsPanel.tsx
import { useTargetAuthEventsQuery } from "../api.auth-events";
import { AuthEventPill } from "./AuthEventPill";
import styles from "./TargetAuthEventsPanel.module.css";

export function TargetAuthEventsPanel({ targetId }: { targetId: string }) {
  const query = useTargetAuthEventsQuery(targetId);
  const data = query.data;
  if (!data || data.count === 0) return null;
  const shown = data.results.length;
  const remaining = data.count - shown;
  return (
    <section
      className={styles.section}
      data-testid="target-auth-events-section"
    >
      <h3>Auth events for target ({data.count})</h3>
      <div className={styles.list}>
        {data.results.map((e) => (
          <AuthEventPill key={e.id} event={e} />
        ))}
      </div>
      {data.next !== null && remaining > 0 && (
        <p
          className={styles.footer}
          data-testid="target-auth-events-more"
        >
          +{remaining} more in the full events feed below.
        </p>
      )}
    </section>
  );
}
```

```css
/* TargetAuthEventsPanel.module.css */
.section { display: flex; flex-direction: column; gap: 0.5rem; margin-block: 1rem; }
.list    { display: flex; flex-direction: column; gap: 0.5rem; }
.footer  { margin: 0; font-size: var(--text-small); opacity: 0.7; }
```

- [ ] **Step 4: Run empty-state test, confirm it passes**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Add populated + ordering + truncation + error tests**

Continue in [task-3-panel-component-tests.md](task-3-panel-component-tests.md). Return here for Step 6 (commit).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.tsx \
        frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.module.css \
        frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx
git commit -m "feat(frontend): TargetAuthEventsPanel — list + empty + +N more footer"
```
