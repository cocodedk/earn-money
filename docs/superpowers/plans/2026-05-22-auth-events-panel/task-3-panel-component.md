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
import { screen } from "@testing-library/react";
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

async function flushQuery() {
  await new Promise((r) => setTimeout(r, 0));
}

describe("TargetAuthEventsPanel", () => {
  it("renders nothing when count is 0", async () => {
    server.use(
      msw.get("/api/events/", () => HttpResponse.json(authPage([]))),
    );
    const { container } = renderWithProviders(
      <TargetAuthEventsPanel targetId={TARGET_ID} />,
    );
    await flushQuery();
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

- [ ] **Step 5: Add populated + ordering + truncation tests**

Append:

```tsx
  it("renders one pill per event, newest first (hook reversed)", async () => {
    server.use(
      msw.get("/api/events/", () =>
        HttpResponse.json(
          authPage([
            makeEvent({
              id: "old",
              type: "auth.probe_refused",
              created_at: "2026-05-22T08:00:00Z",
            }),
            makeEvent({
              id: "new",
              type: "auth.finding_candidate",
              created_at: "2026-05-22T10:00:00Z",
            }),
          ]),
        ),
      ),
    );
    renderWithProviders(<TargetAuthEventsPanel targetId={TARGET_ID} />);
    const buttons = await screen.findAllByRole("button");
    expect(buttons).toHaveLength(2);
    expect(buttons[0]).toHaveTextContent("Finding candidate");
    expect(buttons[1]).toHaveTextContent("Probe refused");
    expect(
      screen.getByRole("heading", { name: /Auth events for target \(2\)/ }),
    ).toBeInTheDocument();
  });

  it("shows +N more footer when next is non-null and remaining > 0", async () => {
    const rows = Array.from({ length: 50 }, (_, i) =>
      makeEvent({
        id: `e${i}`,
        type: "auth.probe_refused",
        created_at: `2026-05-22T0${i % 10}:00:00Z`,
      }),
    );
    server.use(
      msw.get("/api/events/", () =>
        HttpResponse.json({
          count: 73,
          next: "/api/events/?page=2",
          previous: null,
          results: rows,
        }),
      ),
    );
    renderWithProviders(<TargetAuthEventsPanel targetId={TARGET_ID} />);
    const more = await screen.findByTestId("target-auth-events-more");
    expect(more).toHaveTextContent("+23 more in the full events feed below.");
  });

  it("hides +N footer when next is null", async () => {
    server.use(
      msw.get("/api/events/", () =>
        HttpResponse.json(
          authPage([makeEvent({ type: "auth.probe_refused" })], null),
        ),
      ),
    );
    renderWithProviders(<TargetAuthEventsPanel targetId={TARGET_ID} />);
    await screen.findByRole("button");
    expect(screen.queryByTestId("target-auth-events-more")).toBeNull();
  });
```

- [ ] **Step 6: Run all panel tests with coverage**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx --coverage
```
Expected: 4/4 PASS; panel + CSS at 100% branch coverage.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.tsx \
        frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.module.css \
        frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx
git commit -m "feat(frontend): TargetAuthEventsPanel — list + empty + +N more footer"
```
