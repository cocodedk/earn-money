# Phase 1 — Types + routes

### Task A: ScanRun types + scanRunsNew route

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/app/routes.ts`

- [ ] **Step 1: Append to `types/api.ts`**

```ts
export type ScanRun = {
  id: Uuid;
  project: Uuid;
  stub_slug: string;
  status: ScanRunStatus;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
  target_run_count: number;
  findings_count: number;
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type CreateScanRunBody = {
  project: Uuid;
  stub_slug: string;
  target_ids: Uuid[];
};

export type LifecycleAction = "start" | "pause" | "resume" | "stop";
```

- [ ] **Step 2: Add `scanRunsNew` to `routes.ts`**

```ts
scanRunsNew: "/scan-runs/new",
```

Also add the path-builder helper next to `stubDetailPath`:
```ts
export const scanRunDetailPath = (id: string) => `/scan-runs/${id}`;
```

The detail-path is unused this slice — the Open button consumes it but the detail route is still ComingSoon. Adding it here keeps phase 3 free of route-string magic.

- [ ] **Step 3: Verify build green**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(frontend): add ScanRun types + scanRunsNew route"
```
