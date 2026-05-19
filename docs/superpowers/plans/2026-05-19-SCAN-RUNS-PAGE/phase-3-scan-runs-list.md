# Phase 3 — ScanRunsList page

### Task C: List with state-machine action buttons

**Files:**
- Create: `frontend/src/features/scan-runs/StatusBadge.tsx`
- Create: `frontend/src/features/scan-runs/StatusBadge.test.tsx`
- Create: `frontend/src/features/scan-runs/ScanRunsList.tsx`
- Create: `frontend/src/features/scan-runs/ScanRunsList.test.tsx`

- [ ] **Step 1: StatusBadge wrapper + test**

`features/scan-runs/StatusBadge.tsx`:

```tsx
import { StatusBadge as GenericStatusBadge } from "../../components/StatusBadge";
import type { ScanRunStatus } from "../../types/api";

const STATUS_PALETTE: Record<ScanRunStatus, string> = {
  queued: "bg-gray-200 text-gray-700",
  running: "bg-blue-100 text-blue-800",
  paused: "bg-yellow-100 text-yellow-800",
  stopping: "bg-orange-100 text-orange-800",
  stopped: "bg-gray-200 text-gray-700",
  failed: "bg-red-100 text-red-800",
  done: "bg-green-100 text-green-800",
};

export function StatusBadge({ status }: { status: ScanRunStatus }) {
  return <GenericStatusBadge status={status} palette={STATUS_PALETTE} />;
}
```

Test mirrors Stubs' palette test (`it.each` over the 7 statuses).

- [ ] **Step 2: ScanRunsList — failing test first**

`ScanRunsList.test.tsx` covers:
- loading → skeleton
- empty → EmptyState with Create scan run button → click navigates to /scan-runs/new
- error → BackendUnreachableCallout with Retry
- happy → rows; project + stub joined; status badges rendered; ID short = first 8 chars
- one test per status (queued / running / paused / stopping / stopped / failed / done) confirming the exact button set per the state machine
- click Start → MSW handler returns the updated row; row state flips on refetch
- click Stop on a running row → same
- 400 from an illegal transition → surfaces an inline error

The test file uses the existing `withPaginated`, `LocationProbe`, and `makeScanRun` factory. Filtered by status via `withPaginated("/api/scan-runs/", [makeScanRun({ status: "running" })])`. The four lifecycle hooks each get a per-test MSW override.

- [ ] **Step 3: Implement `ScanRunsList.tsx`**

Key shape:

```tsx
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES, scanRunDetailPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { BackendUnreachableCallout } from "../../components/Callout";
import { useProjectsQuery } from "../projects/api";
import { useStubsQuery } from "../stubs/api";
import {
  usePauseScanRunMutation,
  useResumeScanRunMutation,
  useScanRunsQuery,
  useStartScanRunMutation,
  useStopScanRunMutation,
} from "./api";
import { StatusBadge } from "./StatusBadge";
import type { Project, ScanRun, ScanRunStatus, StubSummary } from "../../types/api";

const VALID_ACTIONS: Record<ScanRunStatus, readonly LifecycleAction[]> = {
  queued: ["start"],
  running: ["pause", "stop"],
  paused: ["resume", "stop"],
  stopping: [],
  stopped: [],
  failed: [],
  done: [],
};

type LifecycleAction = "start" | "pause" | "resume" | "stop";

// ActionButtons renders the visible lifecycle controls per the state
// machine. Each button calls one of the four mutation hooks; cache
// invalidation drives the row re-render.
function ActionButtons({ run }: { run: ScanRun }) {
  const start = useStartScanRunMutation();
  const pause = usePauseScanRunMutation();
  const resume = useResumeScanRunMutation();
  const stop = useStopScanRunMutation();
  const handlers: Record<LifecycleAction, () => void> = {
    start: () => start.mutate(run.id),
    pause: () => pause.mutate(run.id),
    resume: () => resume.mutate(run.id),
    stop: () => stop.mutate(run.id),
  };
  return (
    <div className="flex gap-2">
      <ButtonLink to={scanRunDetailPath(run.id)} variant="secondary">
        Open
      </ButtonLink>
      {VALID_ACTIONS[run.status].map((action) => (
        <button
          key={action}
          type="button"
          onClick={handlers[action]}
          className="rounded bg-gray-200 px-3 py-1 text-sm hover:bg-gray-300"
        >
          {action.charAt(0).toUpperCase() + action.slice(1)}
        </button>
      ))}
    </div>
  );
}
```

Plus `buildColumns(projectName, stubTitle)` with 9 columns matching the spec, the standard query-error / empty / loading branches, and a `useMemo` on columns keyed to the lookup helpers.

- [ ] **Step 4: Coverage 100%**

```bash
cd frontend && npm test -- src/features/scan-runs/ScanRunsList --coverage
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(frontend): add ScanRunsList with state-machine action buttons"
```
