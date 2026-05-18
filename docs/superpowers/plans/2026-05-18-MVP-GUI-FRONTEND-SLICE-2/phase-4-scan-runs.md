# Phase 4 — Scan Runs CRUD + lifecycle

`/scan-runs/` list + `/scan-runs/new` create + lifecycle action API. Peer's contract per `f351ea6` / `10317c0`:
- `GET /api/scan-runs/?project=<uuid>&status=<status>&stub_slug=<slug>` paginated
- `POST /api/scan-runs/` body `{project, stub_slug, target_ids}`
- `POST /api/scan-runs/<id>/{start,pause,resume,stop}/` — 400 with `{detail}` on invalid transition

---

### Task K: ScanRuns API client + lifecycle hooks

**Files:**
- Create: `frontend/src/features/scan-runs/api.ts`
- Create: `frontend/src/features/scan-runs/api.test.tsx`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add types**

```ts
export type ScanRun = {
  id: Uuid;
  project: Uuid;
  stub_slug: string;
  status: ScanRunStatus;
  target_run_count: number;
  findings_count: number;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
  created_at: Iso8601;
};

export type CreateScanRunBody = {
  project: Uuid;
  stub_slug: string;
  target_ids: Uuid[];
};

export type LifecycleAction = "start" | "pause" | "resume" | "stop";
```

- [ ] **Step 2: Test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import {
  useScanRunsQuery,
  useScanRunDetailQuery,
  useCreateScanRunMutation,
  useScanRunLifecycleMutation,
  SCAN_RUNS_KEY,
} from "./api";

describe("useScanRunsQuery", () => {
  it("fetches with project filter", async () => {
    let url: URL | null = null;
    server.use(
      msw.get("/api/scan-runs/", ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useScanRunsQuery({ project: "p1" }), { wrapper: Wrapper });
    await waitFor(() => expect(url).not.toBeNull());
    expect(url?.searchParams.get("project")).toBe("p1");
  });
});

describe("useScanRunDetailQuery", () => {
  it("fetches by id", async () => {
    server.use(
      msw.get("/api/scan-runs/r1/", () =>
        HttpResponse.json({
          id: "r1",
          project: "p1",
          stub_slug: "1.1",
          status: "queued",
          target_run_count: 0,
          findings_count: 0,
          started_at: null,
          finished_at: null,
          created_at: "2026-05-18T20:00:00.000000Z",
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useScanRunDetailQuery("r1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.id).toBe("r1"));
  });
});

describe("useCreateScanRunMutation", () => {
  it("POSTs and invalidates scan-runs + projects", async () => {
    server.use(
      msw.post("/api/scan-runs/", () =>
        HttpResponse.json(
          {
            id: "r-new",
            project: "p1",
            stub_slug: "1.1",
            status: "queued",
            target_run_count: 1,
            findings_count: 0,
            started_at: null,
            finished_at: null,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        ),
      ),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateScanRunMutation(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        project: "p1",
        stub_slug: "1.1",
        target_ids: ["t1"],
      });
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: SCAN_RUNS_KEY });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});

describe("useScanRunLifecycleMutation", () => {
  it("POSTs to the action endpoint and invalidates detail", async () => {
    let posted = false;
    server.use(
      msw.post("/api/scan-runs/r1/start/", () => {
        posted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useScanRunLifecycleMutation("r1"), {
      wrapper: Wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync("start");
    });
    expect(posted).toBe(true);
    expect(spy).toHaveBeenCalledWith({ queryKey: [...SCAN_RUNS_KEY, "r1"] });
  });
});
```

- [ ] **Step 3: Implement `api.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import { PROJECTS_KEY } from "../projects/api";
import type {
  CreateScanRunBody,
  LifecycleAction,
  Paginated,
  ScanRun,
  ScanRunStatus,
  Uuid,
} from "../../types/api";

export const SCAN_RUNS_KEY = ["scan-runs"] as const;

type ScanRunsFilter = {
  project?: Uuid;
  status?: ScanRunStatus;
  stub_slug?: string;
};

export function useScanRunsQuery(filter: ScanRunsFilter = {}) {
  const search = new URLSearchParams();
  if (filter.project) search.set("project", filter.project);
  if (filter.status) search.set("status", filter.status);
  if (filter.stub_slug) search.set("stub_slug", filter.stub_slug);
  const qs = search.toString();
  const url = qs ? `/api/scan-runs/?${qs}` : "/api/scan-runs/";
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, filter] as const,
    queryFn: () => http<Paginated<ScanRun>>(url),
  });
}

export function useScanRunDetailQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id] as const,
    queryFn: () => http<ScanRun>(`/api/scan-runs/${id!}/`),
    enabled: Boolean(id),
  });
}

export function useCreateScanRunMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateScanRunBody) =>
      http<ScanRun>("/api/scan-runs/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY });
      void client.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}

export function useScanRunLifecycleMutation(id: Uuid) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: LifecycleAction) =>
      http<void>(`/api/scan-runs/${id}/${action}/`, { method: "POST" }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [...SCAN_RUNS_KEY, id] });
      void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY });
    },
  });
}
```

- [ ] **Step 4: Commit + /simplify**

```bash
npm run test -- src/features/scan-runs/api
git add frontend/src/features/scan-runs/api.{ts,test.tsx} frontend/src/types/api.ts
git commit -m "feat(frontend): add ScanRuns API client + lifecycle hooks"
```

---

### Task L: `ScanRunsList` page

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunsList.tsx`
- Create: `frontend/src/features/scan-runs/ScanRunsList.test.tsx`

The list filters by the current project (default), shows status badges, exposes a "Create scan run" entry. Each row links to `/scan-runs/<id>`.

- [ ] **Step 1: Test** — 4 cases analogous to TargetsList: loading skeleton, empty state with Create action, error retry, rows render with StatusBadge + row link to detail. (Test body follows the same pattern as `phase-2-targets.md` Task F's tests — copy-paste and adjust paths/fields.)

- [ ] **Step 2: Implement `ScanRunsList.tsx`**

```tsx
import { Link, useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { StatusBadge } from "../../components/StatusBadge";
import { useScanRunsQuery } from "./api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import type { ScanRun } from "../../types/api";

const columns: TableColumn<ScanRun>[] = [
  {
    key: "id",
    header: "ID",
    cell: (r) => (
      <Link to={`/scan-runs/${r.id}`} className="font-mono text-blue-700 hover:underline">
        {r.id.slice(0, 8)}
      </Link>
    ),
  },
  { key: "stub_slug", header: "Stub", cell: (r) => r.stub_slug },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge status={r.status} />,
  },
  { key: "target_run_count", header: "Targets", cell: (r) => r.target_run_count },
  { key: "findings_count", header: "Findings", cell: (r) => r.findings_count },
  {
    key: "started_at",
    header: "Started at",
    cell: (r) => (r.started_at ? r.started_at.slice(0, 19).replace("T", " ") : "—"),
  },
  {
    key: "finished_at",
    header: "Finished at",
    cell: (r) => (r.finished_at ? r.finished_at.slice(0, 19).replace("T", " ") : "—"),
  },
];

export function ScanRunsList() {
  const { id: projectId } = useCurrentProject();
  const query = useScanRunsQuery(projectId ? { project: projectId } : {});
  const navigate = useNavigate();
  return (
    <>
      <PageHeader
        title="Scan runs"
        action={
          <ButtonLink to={ROUTES.scanRunsNew} data-testid="page-header-create">
            Create scan run
          </ButtonLink>
        }
      />
      <div className="mt-4">
        {query.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load scan runs.
          </Callout>
        ) : (
          <Table<ScanRun>
            columns={columns}
            rows={query.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={query.isLoading}
            emptyState={
              <EmptyState
                message="No scan runs yet."
                action={{
                  label: "Create scan run",
                  onClick: () => navigate(ROUTES.scanRunsNew),
                }}
              />
            }
          />
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 3: Add `ROUTES.scanRunsNew` + `ROUTES.scanRunDetail(id)` helpers** to `src/app/routes.ts`:

```ts
export const ROUTES = {
  index: "/",
  projects: "/projects",
  projectsNew: "/projects/new",
  targets: "/targets",
  targetsNew: "/targets/new",
  stubs: "/stubs",
  scanRuns: "/scan-runs",
  scanRunsNew: "/scan-runs/new",
  scanRunDetail: (id: string) => `/scan-runs/${id}`,
  findings: "/findings",
  evidence: "/evidence",
  settings: "/settings",
} as const;
```

- [ ] **Step 4: Commit + /simplify**

```bash
git add frontend/src/features/scan-runs/ScanRunsList.{tsx,test.tsx} frontend/src/app/routes.ts
git commit -m "feat(frontend): add ScanRunsList page"
```

---

### Task M: `CreateScanRun` form with `MultiTargetSelect`

**Files:**
- Create: `frontend/src/features/scan-runs/CreateScanRun.tsx`
- Create: `frontend/src/features/scan-runs/CreateScanRun.test.tsx`
- Create: `frontend/src/features/scan-runs/MultiTargetSelect.tsx`

The form fields: stub_slug (dropdown over `/api/stubs/`), target_ids (multi-checkbox over active targets in the current project). Project comes from `useCurrentProject` — no explicit field. "Create and start" submits + invokes the start lifecycle in one click.

- [ ] **Step 1: Test** — 6 cases (per spec validation rules in `05-scan-runs.md`):
  1. Blocks when no current project.
  2. Validates `stub_slug` is required.
  3. Validates at least one target is required (selection mode = "selected").
  4. Defaults to "all active targets" selection mode.
  5. Submits → routes to `/scan-runs/<new-id>`.
  6. "Create and start" → POST `/api/scan-runs/`, then POST `/api/scan-runs/<id>/start/`, then route.

- [ ] **Step 2: Implement `MultiTargetSelect.tsx`** as a controlled checkbox list keyed by target.id with a "select all / clear all" toggle row.

- [ ] **Step 3: Implement `CreateScanRun.tsx`** — fetch active targets via `useTargetsQuery(projectId)` filtered client-side to `status === "active"`, render `<select>` over `useStubsQuery()`, run mutation + optional lifecycle start, navigate to detail.

- [ ] **Step 4: Run + commit + /simplify**

---

### Task N: Wire route paths into `App.tsx` (deferred to phase 7 integration). No code change here — just confirm routes line up with the constants added in Task L Step 3.
