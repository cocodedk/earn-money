# Phase 7 — Integration

Wire the new pages into `App.tsx`, replace five `ComingSoon` placeholders, add an end-to-end happy-path test that exercises the entire slice 2 workflow against MSW.

---

### Task T: Replace ComingSoon routes with real pages

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update routes**

```tsx
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ROUTES } from "./app/routes";
import { ProjectsList } from "./features/projects/ProjectsList";
import { CreateProject } from "./features/projects/CreateProject";
import { TargetsList } from "./features/targets/TargetsList";
import { AddTarget } from "./features/targets/AddTarget";
import { StubsList } from "./features/stubs/StubsList";
import { StubDetail } from "./features/stubs/StubDetail";
import { ScanRunsList } from "./features/scan-runs/ScanRunsList";
import { CreateScanRun } from "./features/scan-runs/CreateScanRun";
import { ScanRunDetail } from "./features/scan-runs/ScanRunDetail";
import { ComingSoon } from "./features/coming-soon";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to={ROUTES.projects} replace />} />
        <Route path={ROUTES.projects} element={<ProjectsList />} />
        <Route path={ROUTES.projectsNew} element={<CreateProject />} />
        <Route path={ROUTES.targets} element={<TargetsList />} />
        <Route path={ROUTES.targetsNew} element={<AddTarget />} />
        <Route path={ROUTES.stubs} element={<StubsList />} />
        <Route path="/stubs/:slug" element={<StubDetail />} />
        <Route path={ROUTES.scanRuns} element={<ScanRunsList />} />
        <Route path={ROUTES.scanRunsNew} element={<CreateScanRun />} />
        <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
        <Route path={ROUTES.findings} element={<ComingSoon name="Findings" />} />
        <Route path={ROUTES.evidence} element={<ComingSoon name="Evidence" />} />
        <Route path={ROUTES.settings} element={<ComingSoon name="Settings" />} />
        <Route path="*" element={<ComingSoon name="Not found" />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 2: Commit + /simplify**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): wire slice-2 routes into App"
```

---

### Task U: Slice-2 end-to-end happy path test

**Files:**
- Create: `frontend/src/App.slice2.e2e.test.tsx`

Single test that walks the full operator path through MSW:
1. Render `<App/>` at `/projects` with one seeded project + localStorage current-project set.
2. Click "Set as current" — chip shows project name.
3. Navigate to `/targets` via sidebar — empty state visible.
4. Click "Add target" → form → fill `https://dvwa.cocode.dk` → submit → land back on `/targets` with the new row.
5. Navigate to `/stubs` → see "Framework detection" row → click → land on `/stubs/1.1` → body visible.
6. Navigate to `/scan-runs` → empty state → click "Create scan run" → form → select stub `1.1` → submit.
7. Land on `/scan-runs/<new-id>` → header shows status `queued` → click Start → status flips to `running`.
8. SSE mock emits two events → both visible in the live events panel.
9. Mutation hits stop endpoint → status flips to `stopped`.

The test is verbose (~150 lines) but exercises every wired-up integration point.

- [ ] **Step 1: Write the test**
- [ ] **Step 2: Run + commit + /simplify**

```bash
git add frontend/src/App.slice2.e2e.test.tsx
git commit -m "test(frontend): add slice-2 end-to-end happy path"
```

---

### Task V: Coverage gap sweep

Run the full suite with coverage. Any file under 100% gets an additional test. Common patterns to check:
- Conditional rendering branches in panels (loading vs error vs empty vs populated)
- SSE polling-fallback branch in `useScanRunEvents`
- Lifecycle button visibility per status

- [ ] **Step 1: `npm run test:coverage`**
- [ ] **Step 2: Address gaps with targeted tests, commit each as `test(frontend): cover <branch>`**.
- [ ] **Step 3: Final commit + /simplify until clean**.
