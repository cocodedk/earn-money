# Task 2 — `AuthEventPill` component

**Goal:** A single-event row that renders a collapsed coloured pill (severity-driven variant), and on click / Enter / Space expands to show `event.message` and pretty-printed `event.data`.

**Files:**
- Create: `frontend/src/features/targets/TargetResult/AuthEventPill.tsx`
- Create: `frontend/src/features/targets/TargetResult/AuthEventPill.module.css`
- Test: `frontend/src/features/targets/TargetResult/AuthEventPill.test.tsx`

## Severity mapping (from spec)

| `event.type`               | `data-variant` | meaning           |
|----------------------------|----------------|-------------------|
| `auth.probe_refused`       | `warning`      | RoE / policy      |
| `auth.fixture_required`    | `info`         | needs config      |
| `auth.finding_candidate`   | `alert`        | possible vuln     |
| anything else              | `info`         | safe fallback     |

## Steps

- [ ] **Step 1: Write the failing collapsed-render test**

```tsx
// AuthEventPill.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthEventPill } from "./AuthEventPill";
import { makeEvent } from "../../scan-runs/__fixtures__/event";

describe("AuthEventPill", () => {
  it("collapsed shows type label and timestamp", () => {
    render(
      <AuthEventPill
        event={makeEvent({
          type: "auth.probe_refused",
          created_at: "2026-05-22T10:15:00Z",
        })}
      />,
    );
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Probe refused")).toBeInTheDocument();
    expect(screen.getByTestId("auth-event-pill-time")).toHaveTextContent(/\d{1,2}:\d{2}/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult/AuthEventPill.test.tsx
```
Expected: FAIL — `AuthEventPill` not defined.

- [ ] **Step 3: Write the minimal pill component**

```tsx
// AuthEventPill.tsx
import { useId, useState } from "react";
import type { Event } from "../../../types/api";
import styles from "./AuthEventPill.module.css";

const LABELS: Record<string, string> = {
  "auth.probe_refused": "Probe refused",
  "auth.fixture_required": "Fixture required",
  "auth.finding_candidate": "Finding candidate",
};

const VARIANTS: Record<string, "warning" | "info" | "alert"> = {
  "auth.probe_refused": "warning",
  "auth.fixture_required": "info",
  "auth.finding_candidate": "alert",
};

function fmtTime(ts: string): string {
  return new Date(ts).toLocaleTimeString();
}

export function AuthEventPill({ event }: { event: Event }) {
  const detailId = useId();
  const [expanded, setExpanded] = useState(false);
  const variant = VARIANTS[event.type] ?? "info";
  const label = LABELS[event.type] ?? event.type;
  const payload = event.data ?? {};
  return (
    <div className={styles.row} data-variant={variant}>
      <button
        type="button"
        className={styles.pill}
        aria-expanded={expanded}
        aria-controls={expanded ? detailId : undefined}
        onClick={() => setExpanded((v) => !v)}
      >
        <span className={styles.label}>{label}</span>
        <span className={styles.time} data-testid="auth-event-pill-time">
          {fmtTime(event.created_at)}
        </span>
      </button>
      {expanded && (
        <div id={detailId} className={styles.detail} data-testid="auth-event-pill-detail">
          <p>{event.message}</p>
          <pre>{JSON.stringify(payload, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
```

```css
/* AuthEventPill.module.css */
.row { display: flex; flex-direction: column; gap: 0.25rem; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill, 999px);
  background: transparent;
  font-family: var(--font-mono);
  font-size: var(--text-small);
  cursor: pointer;
}
.row[data-variant="warning"] .pill { color: var(--color-warning); border-color: var(--color-warning); }
.row[data-variant="info"]    .pill { color: var(--color-info);    border-color: var(--color-info); }
.row[data-variant="alert"]   .pill { color: var(--color-alert);   border-color: var(--color-alert); }
.label { font-weight: 600; }
.time  { opacity: 0.7; }
.detail { padding: 0.5rem; background: var(--color-surface-elev-1); border-radius: var(--radius-card, 0.5rem); }
.detail pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult/AuthEventPill.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Add variant + interaction + a11y tests, run with coverage**

Continue in [task-2-pill-component-tests.md](task-2-pill-component-tests.md). Return here for Step 6 (commit).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/targets/TargetResult/AuthEventPill.tsx \
        frontend/src/features/targets/TargetResult/AuthEventPill.module.css \
        frontend/src/features/targets/TargetResult/AuthEventPill.test.tsx
git commit -m "feat(frontend): AuthEventPill — 3 severity variants + expand-in-place"
```
