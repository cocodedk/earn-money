# Phase 0 — Primitives

Three primitives slice 2's pages will reuse. Each follows the slice-1 folder convention: `src/components/<Name>/{Name.tsx, Name.module.css, Name.test.tsx, index.ts}`.

---

### Task A: Extend `StatusBadge` (existing) with `scan_target_run.failed` payload + tooltip

The `StatusBadge` primitive already exists conceptually in `19-component-primitives.md` (typed enum prop, color from the token map). Slice 1 didn't create it — only `ConnectionPill`, `CurrentProjectChip`, `Button`, etc. Slice 2 introduces it.

**Files:**
- Create: `frontend/src/components/StatusBadge/StatusBadge.tsx`
- Create: `frontend/src/components/StatusBadge/StatusBadge.module.css`
- Create: `frontend/src/components/StatusBadge/StatusBadge.test.tsx`
- Create: `frontend/src/components/StatusBadge/index.ts`

- [ ] **Step 1: Write `StatusBadge.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["queued", "Queued"],
    ["running", "Running"],
    ["paused", "Paused"],
    ["stopping", "Stopping"],
    ["stopped", "Stopped"],
    ["failed", "Failed"],
    ["done", "Done"],
  ] as const)("renders the %s status", (status, label) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByTestId("status-badge");
    expect(badge).toHaveAttribute("data-status", status);
    expect(badge).toHaveTextContent(label);
  });

  it("renders tooltip content from error + message when failed", () => {
    render(
      <StatusBadge
        status="failed"
        failure={{ error: "ConnectError", message: "timeout" }}
      />,
    );
    const badge = screen.getByTestId("status-badge");
    expect(badge).toHaveAttribute(
      "title",
      "ConnectError: timeout",
    );
  });

  it("omits tooltip when failure is not provided", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByTestId("status-badge")).not.toHaveAttribute("title");
  });

  it("ignores failure prop when status is not failed", () => {
    render(
      <StatusBadge
        status="done"
        failure={{ error: "X", message: "y" }}
      />,
    );
    expect(screen.getByTestId("status-badge")).not.toHaveAttribute("title");
  });
});
```

- [ ] **Step 2: Run, see fail**

```bash
npm run test -- src/components/StatusBadge
```

Expected: FAIL "Cannot find module './StatusBadge'".

- [ ] **Step 3: Implement `StatusBadge.tsx`**

```tsx
import styles from "./StatusBadge.module.css";
import type { ScanRunStatus, TargetStatus } from "../../types/api";

export type StatusBadgeStatus = ScanRunStatus | TargetStatus;

export type StatusBadgeFailure = { error: string; message: string };

export type StatusBadgeProps = {
  status: StatusBadgeStatus;
  failure?: StatusBadgeFailure;
};

const labelByStatus: Record<StatusBadgeStatus, string> = {
  queued: "Queued",
  running: "Running",
  paused: "Paused",
  stopping: "Stopping",
  stopped: "Stopped",
  failed: "Failed",
  done: "Done",
  active: "Active",
  retired: "Retired",
};

export function StatusBadge({ status, failure }: StatusBadgeProps) {
  const tooltip =
    status === "failed" && failure
      ? `${failure.error}: ${failure.message}`
      : undefined;
  return (
    <span
      className={`${styles.badge} ${styles[status]}`}
      data-testid="status-badge"
      data-status={status}
      title={tooltip}
    >
      {labelByStatus[status]}
    </span>
  );
}
```

- [ ] **Step 4: Implement `StatusBadge.module.css`**

```css
.badge {
  @apply inline-flex items-center px-2 h-6 rounded text-xs font-medium;
}
.queued,
.stopped {
  @apply bg-gray-100 text-gray-700;
}
.running {
  @apply bg-blue-100 text-blue-700;
}
.paused {
  @apply bg-yellow-100 text-yellow-800;
}
.stopping {
  @apply bg-orange-100 text-orange-800;
}
.failed {
  @apply bg-red-100 text-red-700;
}
.done {
  @apply bg-green-100 text-green-700;
}
.active {
  @apply bg-green-100 text-green-700;
}
.retired {
  @apply bg-gray-100 text-gray-600;
}
```

- [ ] **Step 5: `index.ts`**

```ts
export * from "./StatusBadge";
```

- [ ] **Step 6: Run + commit**

```bash
npm run test -- src/components/StatusBadge
git add frontend/src/components/StatusBadge/
git commit -m "feat(frontend): add StatusBadge with scan-target failure tooltip"
```

- [ ] **Step 7: /simplify**, fix any findings, commit each round.

---

### Task B: `SeverityBadge`

Tightens the severity colour map from `18-design-tokens.md` behind a typed enum prop. Used by the Findings panel on the scan-run detail page.

**Files:**
- Create: `frontend/src/components/SeverityBadge/SeverityBadge.tsx`
- Create: `frontend/src/components/SeverityBadge/SeverityBadge.module.css`
- Create: `frontend/src/components/SeverityBadge/SeverityBadge.test.tsx`
- Create: `frontend/src/components/SeverityBadge/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeverityBadge } from "./SeverityBadge";

describe("SeverityBadge", () => {
  it.each([
    ["info", "Info"],
    ["low", "Low"],
    ["medium", "Medium"],
    ["high", "High"],
    ["critical", "Critical"],
  ] as const)("renders the %s severity", (severity, label) => {
    render(<SeverityBadge severity={severity} />);
    const badge = screen.getByTestId("severity-badge");
    expect(badge).toHaveAttribute("data-severity", severity);
    expect(badge).toHaveTextContent(label);
  });
});
```

- [ ] **Step 2: Implement `SeverityBadge.tsx`**

```tsx
import styles from "./SeverityBadge.module.css";
import type { Severity } from "../../types/api";

export type SeverityBadgeProps = { severity: Severity };

const labelBySeverity: Record<Severity, string> = {
  info: "Info",
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  return (
    <span
      className={`${styles.badge} ${styles[severity]}`}
      data-testid="severity-badge"
      data-severity={severity}
    >
      {labelBySeverity[severity]}
    </span>
  );
}
```

- [ ] **Step 3: `SeverityBadge.module.css`**

```css
.badge {
  @apply inline-flex items-center px-2 h-6 rounded text-xs font-medium;
}
.info {
  @apply bg-gray-100 text-gray-700;
}
.low {
  @apply bg-blue-100 text-blue-700;
}
.medium {
  @apply bg-yellow-100 text-yellow-800;
}
.high {
  @apply bg-orange-100 text-orange-800;
}
.critical {
  @apply bg-red-100 text-red-700;
}
```

- [ ] **Step 4: `index.ts`**

```ts
export * from "./SeverityBadge";
```

- [ ] **Step 5: Run + commit + /simplify**

```bash
npm run test -- src/components/SeverityBadge
git add frontend/src/components/SeverityBadge/
git commit -m "feat(frontend): add SeverityBadge primitive"
```

---

### Task C: `EventList`

Rolling log component for the scan-run detail Live Events panel. Shows a fixed-height scrollable list of events with auto-scroll toggle and a level filter.

**Files:**
- Create: `frontend/src/components/EventList/EventList.tsx`
- Create: `frontend/src/components/EventList/EventList.module.css`
- Create: `frontend/src/components/EventList/EventList.test.tsx`
- Create: `frontend/src/components/EventList/index.ts`
- Modify: `frontend/src/types/api.ts` (add `ScanEvent` type)

- [ ] **Step 1: Add `ScanEvent` type to `src/types/api.ts`**

```ts
export type ScanEventLevel = "debug" | "info" | "warning" | "error";

export type ScanEvent = {
  id: Uuid;
  scan_run_id: Uuid;
  target_id: Uuid | null;
  level: ScanEventLevel;
  event_type: string;
  message: string;
  data: Record<string, unknown>;
  created_at: Iso8601;
};
```

- [ ] **Step 2: Test `EventList`**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EventList } from "./EventList";
import type { ScanEvent } from "../../types/api";

const events: ScanEvent[] = [
  {
    id: "e1",
    scan_run_id: "r1",
    target_id: "t1",
    level: "info",
    event_type: "target_started",
    message: "Started",
    data: {},
    created_at: "2026-05-18T20:00:00.000000Z",
  },
  {
    id: "e2",
    scan_run_id: "r1",
    target_id: "t1",
    level: "error",
    event_type: "scan_target_run.failed",
    message: "Boom",
    data: {},
    created_at: "2026-05-18T20:00:05.000000Z",
  },
];

describe("EventList", () => {
  it("renders each event with timestamp, level, type, message", () => {
    render(<EventList events={events} />);
    const rows = screen.getAllByTestId("event-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("info");
    expect(rows[0]).toHaveTextContent("target_started");
    expect(rows[1]).toHaveTextContent("error");
    expect(rows[1]).toHaveTextContent("Boom");
  });

  it("filters by minimum level when filter is set", async () => {
    render(<EventList events={events} />);
    await userEvent.selectOptions(screen.getByLabelText("Level"), "error");
    const rows = screen.getAllByTestId("event-row");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("error");
  });

  it("renders the empty state when no events", () => {
    render(<EventList events={[]} />);
    expect(screen.getByText(/no events/i)).toBeInTheDocument();
  });

  it("toggles auto-scroll", async () => {
    render(<EventList events={events} />);
    const toggle = screen.getByRole("checkbox", { name: /auto-scroll/i });
    expect(toggle).toBeChecked();
    await userEvent.click(toggle);
    expect(toggle).not.toBeChecked();
  });
});
```

- [ ] **Step 3: Implement `EventList.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import styles from "./EventList.module.css";
import type { ScanEvent, ScanEventLevel } from "../../types/api";

export type EventListProps = { events: ScanEvent[] };

const levelOrder: Record<ScanEventLevel, number> = {
  debug: 0,
  info: 1,
  warning: 2,
  error: 3,
};

const levelOptions: { value: ScanEventLevel | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "debug", label: "Debug" },
  { value: "info", label: "Info" },
  { value: "warning", label: "Warning" },
  { value: "error", label: "Error" },
];

export function EventList({ events }: EventListProps) {
  const [minLevel, setMinLevel] = useState<ScanEventLevel | "all">("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  const visible =
    minLevel === "all"
      ? events
      : events.filter((e) => levelOrder[e.level] >= levelOrder[minLevel]);

  useEffect(() => {
    if (autoScroll && scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [autoScroll, visible.length]);

  return (
    <div className={styles.panel}>
      <div className={styles.controls}>
        <label className={styles.filter}>
          Level
          <select
            value={minLevel}
            onChange={(e) => setMinLevel(e.target.value as ScanEventLevel | "all")}
          >
            {levelOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          Auto-scroll
        </label>
      </div>
      <div className={styles.scroller} ref={scrollerRef}>
        {visible.length === 0 ? (
          <p className={styles.empty}>No events yet.</p>
        ) : (
          <ul className={styles.list}>
            {visible.map((e) => (
              <li
                key={e.id}
                data-testid="event-row"
                data-level={e.level}
                className={styles.row}
              >
                <span className={styles.time}>{e.created_at.slice(11, 19)}</span>
                <span className={styles.level}>{e.level}</span>
                <span className={styles.type}>{e.event_type}</span>
                <span className={styles.message}>{e.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: `EventList.module.css`**

```css
.panel {
  @apply border border-gray-200 rounded;
}
.controls {
  @apply flex items-center gap-4 px-3 py-2 border-b border-gray-200 bg-gray-50 text-sm;
}
.filter {
  @apply flex items-center gap-2;
}
.filter select {
  @apply h-7 border border-gray-300 rounded px-2 bg-white;
}
.toggle {
  @apply flex items-center gap-2;
}
.scroller {
  @apply max-h-72 overflow-y-auto;
}
.list {
  @apply font-mono text-xs;
}
.row {
  @apply grid grid-cols-[68px_60px_180px_1fr] gap-2 px-3 py-1 border-b border-gray-100;
}
.row[data-level="error"] {
  @apply bg-red-50;
}
.row[data-level="warning"] {
  @apply bg-yellow-50;
}
.time {
  @apply text-gray-500;
}
.level {
  @apply text-gray-700 uppercase;
}
.type {
  @apply text-gray-900;
}
.message {
  @apply text-gray-700 truncate;
}
.empty {
  @apply px-3 py-6 text-center text-gray-600;
}
```

- [ ] **Step 5: `index.ts`**

```ts
export * from "./EventList";
```

- [ ] **Step 6: Run + commit + /simplify**

```bash
npm run test -- src/components/EventList
git add frontend/src/components/EventList/ frontend/src/types/api.ts
git commit -m "feat(frontend): add EventList primitive with level filter + auto-scroll"
```
