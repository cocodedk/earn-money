# Phase 6 — Scan Run detail page

The most important MVP page. Six sections per `06-scan-run-detail.md`:
1. Header — scan run ID, project, stub, status, started_at, finished_at
2. Lifecycle controls — Start / Pause / Resume / Stop buttons (only valid ones enabled per status transition rules in `05-scan-runs.md`)
3. Target status table — one row per target_run, status badge per row, links to per-target results (deferred until slice 3, render plain link to a `<ComingSoon/>` placeholder for now)
4. Live events panel — `LiveEventsPanel` from phase 5
5. Findings panel — rows with severity badge + title + status + actions
6. Evidence panel — rows with source + url + matched_value + actions

---

### Task Q: Findings + Evidence read APIs for a scan run

**Files:**
- Modify: `frontend/src/features/scan-runs/api.ts`
- Modify: `frontend/src/features/scan-runs/api.test.tsx`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add types**

```ts
export type Finding = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  stub_slug: string;
  title: string;
  category: string;
  severity: Severity;
  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";
  data: Record<string, unknown>;
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type Evidence = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  finding: Uuid | null;
  source: string;
  url: string | null;
  method: string | null;
  field: string | null;
  matched_value: string | null;
  raw_excerpt: string | null;
  content_hash: string;
  data: Record<string, unknown>;
  created_at: Iso8601;
};

export type TargetRun = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  target_base_url: string;
  status: ScanRunStatus;
  findings_count: number;
  evidence_count: number;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
};
```

- [ ] **Step 2: Add hooks**

```ts
export function useScanRunFindingsQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id, "findings"] as const,
    queryFn: () => http<Paginated<Finding>>(`/api/scan-runs/${id!}/findings/`),
    enabled: Boolean(id),
  });
}

export function useScanRunEvidenceQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id, "evidence"] as const,
    queryFn: () => http<Paginated<Evidence>>(`/api/scan-runs/${id!}/evidence/`),
    enabled: Boolean(id),
  });
}

export function useScanRunTargetRunsQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id, "target-runs"] as const,
    queryFn: () => http<Paginated<TargetRun>>(`/api/scan-runs/${id!}/target-runs/`),
    enabled: Boolean(id),
  });
}
```

If peer's backend exposes `/target-runs/` under a different path, adjust to match — flag in chat if mismatch.

- [ ] **Step 3: Test each hook (3 cases analogous to `useScanRunDetailQuery`). Commit + /simplify.**

---

### Task R: Detail-page sub-components

Split the page across three small files to stay under the 200-line cap.

**Files:**
- Create: `frontend/src/features/scan-runs/detail/ScanRunHeader.tsx`
- Create: `frontend/src/features/scan-runs/detail/LifecycleControls.tsx`
- Create: `frontend/src/features/scan-runs/detail/TargetRunsTable.tsx`
- Create: `frontend/src/features/scan-runs/detail/FindingsPanel.tsx`
- Create: `frontend/src/features/scan-runs/detail/EvidencePanel.tsx`
- Plus matching `.test.tsx` for each.

`ScanRunHeader.tsx` — renders header fields + `StatusBadge`.
`LifecycleControls.tsx` — buttons gated by status transition table:
  - queued → Start
  - running → Pause, Stop
  - paused → Resume, Stop
  - stopping/stopped/failed/done → none enabled
  Uses `useScanRunLifecycleMutation`. Disabled buttons stay rendered (greyed out) to make state machine visible.
`TargetRunsTable.tsx` — table of target_runs with `StatusBadge` per row (including `failed` variant when applicable), counts, started/finished.
`FindingsPanel.tsx` — columns: title, target (foreign-key id truncated), category, `<SeverityBadge/>`, confidence, status, created_at. Empty state "No findings yet."
`EvidencePanel.tsx` — columns: source, target id, url, method, field, matched_value, created_at. Empty state "No evidence yet."

Each sub-component: TDD-first, 100% coverage. Commit each + /simplify.

---

### Task S: Top-level `ScanRunDetail` page composing the sub-components

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunDetail.tsx`
- Create: `frontend/src/features/scan-runs/ScanRunDetail.test.tsx`

```tsx
import { useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import {
  useScanRunDetailQuery,
  useScanRunFindingsQuery,
  useScanRunEvidenceQuery,
  useScanRunTargetRunsQuery,
} from "./api";
import { ScanRunHeader } from "./detail/ScanRunHeader";
import { LifecycleControls } from "./detail/LifecycleControls";
import { TargetRunsTable } from "./detail/TargetRunsTable";
import { FindingsPanel } from "./detail/FindingsPanel";
import { EvidencePanel } from "./detail/EvidencePanel";
import { LiveEventsPanel } from "./LiveEventsPanel";

export function ScanRunDetail() {
  const { id = null } = useParams();
  const runQuery = useScanRunDetailQuery(id);
  const targetRunsQuery = useScanRunTargetRunsQuery(id);
  const findingsQuery = useScanRunFindingsQuery(id);
  const evidenceQuery = useScanRunEvidenceQuery(id);

  if (runQuery.isError || !id) {
    return (
      <>
        <PageHeader title="Scan run" />
        <div className="mt-4">
          <Callout variant="error" title="Not found">
            This scan run could not be loaded.
          </Callout>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Scan run"
        action={runQuery.data && <LifecycleControls scanRun={runQuery.data} />}
      />
      <div className="mt-4 flex flex-col gap-6">
        {runQuery.data && <ScanRunHeader scanRun={runQuery.data} />}
        <section>
          <h2 className="text-lg font-medium mb-2">Targets</h2>
          <TargetRunsTable
            isLoading={targetRunsQuery.isLoading}
            rows={targetRunsQuery.data?.results ?? []}
          />
        </section>
        <section>
          <h2 className="text-lg font-medium mb-2">Live events</h2>
          <LiveEventsPanel scanRunId={id} />
        </section>
        <section>
          <h2 className="text-lg font-medium mb-2">Findings</h2>
          <FindingsPanel
            isLoading={findingsQuery.isLoading}
            rows={findingsQuery.data?.results ?? []}
          />
        </section>
        <section>
          <h2 className="text-lg font-medium mb-2">Evidence</h2>
          <EvidencePanel
            isLoading={evidenceQuery.isLoading}
            rows={evidenceQuery.data?.results ?? []}
          />
        </section>
      </div>
    </>
  );
}
```

Test cases:
1. Renders all five panels with isolated loading + error states (one panel failing doesn't blank the rest).
2. The lifecycle controls fire mutations against the scan run id.
3. The route param shapes the queries.

- [ ] **Run + commit + /simplify**.
