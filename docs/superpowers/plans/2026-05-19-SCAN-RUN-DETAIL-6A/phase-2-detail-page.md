# Phase 2 — ScanRunDetail component

### Task B: Page + tests

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunDetail.tsx`
- Create: `frontend/src/features/scan-runs/ScanRunDetail.test.tsx`

- [ ] **Step 1: Failing test — `ScanRunDetail.test.tsx`**

Covers:
- 404 → "Scan run not found" + back-link to `/scan-runs`
- transport error → `BackendUnreachableCallout`
- loading (no data) → "Loading…" header
- happy queued → header fields populated, project + stub names joined, Start button visible, others hidden
- happy running → Pause + Stop visible; Start/Resume hidden
- happy done → no lifecycle buttons; finished_at rendered
- click Start fires the mutation (verified via MSW handler counter)
- 400 illegal transition → inline error surfaced

Test uses `renderWithProviders` with `<Route path="/scan-runs/:id" element={<ScanRunDetail />} />` plus MSW handlers for `/api/scan-runs/r-1/` (single) and `/api/projects/` + `/api/stubs/` for the joins.

- [ ] **Step 2: Implement `ScanRunDetail.tsx`**

Skeleton (~120 lines):

```tsx
import { Link, useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import {
  BackendUnreachableCallout,
  Callout,
  CalloutSlot,
} from "../../components/Callout";
import { byKey } from "../../lib/byKey";
import { isHttpStatus } from "../../lib/http";
import { useProjectsQuery } from "../projects/api";
import { useStubsQuery } from "../stubs/api";
import { useScanRunQuery } from "./api";
import { useScanRunActions, ACTION_LABEL } from "./useScanRunActions";
import { StatusBadge } from "./StatusBadge";
import type { ScanRun } from "../../types/api";

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 text-sm">
      <span className="w-32 font-medium text-gray-600">{label}</span>
      <span>{children}</span>
    </div>
  );
}

function HeaderActions({ run }: { run: ScanRun }) {
  const { visibleActions, handlers } = useScanRunActions(run);
  if (visibleActions.length === 0) return null;
  return (
    <div className="flex gap-2">
      {visibleActions.map((a) => (
        <button
          key={a}
          type="button"
          onClick={handlers[a]}
          className="rounded bg-gray-200 px-3 py-1 text-sm hover:bg-gray-300"
        >
          {ACTION_LABEL[a]}
        </button>
      ))}
    </div>
  );
}

function DetailHeader({ run }: { run: ScanRun }) {
  const projects = useProjectsQuery();
  const stubs = useStubsQuery();
  const projectName = byKey(
    projects.data?.results,
    (p) => p.id,
    (p) => p.name,
    (id) => id.slice(0, 8),
  );
  const stubName = byKey(
    stubs.data,
    (s) => s.slug,
    (s) => s.slug,
    (slug) => slug,
  );
  return (
    <>
      <PageHeader
        title={`Scan run · ${run.id.slice(0, 8)}`}
        action={<HeaderActions run={run} />}
      />
      <dl className="mt-4 flex flex-col gap-2">
        <MetaRow label="ID">
          <code>{run.id}</code>
        </MetaRow>
        <MetaRow label="Project">{projectName(run.project)}</MetaRow>
        <MetaRow label="Stub">{stubName(run.stub_slug)}</MetaRow>
        <MetaRow label="Status">
          <StatusBadge status={run.status} />
        </MetaRow>
        <MetaRow label="Started at">
          {run.started_at ? run.started_at.slice(0, 19) : "—"}
        </MetaRow>
        <MetaRow label="Finished at">
          {run.finished_at ? run.finished_at.slice(0, 19) : "—"}
        </MetaRow>
      </dl>
    </>
  );
}

export function ScanRunDetail() {
  const { id } = useParams();
  const query = useScanRunQuery(id);

  if (isHttpStatus(query.error, 404)) {
    return (
      <>
        <PageHeader title="Scan run not found" />
        <CalloutSlot>
          <Callout variant="info">
            No scan run matches "{id}".{" "}
            <Link to={ROUTES.scanRuns}>Back to scan runs.</Link>
          </Callout>
        </CalloutSlot>
      </>
    );
  }
  if (query.isError) {
    return (
      <>
        <PageHeader title="Scan run" />
        <CalloutSlot>
          <BackendUnreachableCallout>
            Could not load scan run.
          </BackendUnreachableCallout>
        </CalloutSlot>
      </>
    );
  }
  if (!query.data) {
    return <PageHeader title="Loading…" />;
  }
  return <DetailHeader run={query.data} />;
}
```

- [ ] **Step 3: Coverage 100%**

```bash
cd frontend && npm test -- src/features/scan-runs/ScanRunDetail --coverage
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(frontend): add ScanRunDetail page (header + lifecycle)"
```
