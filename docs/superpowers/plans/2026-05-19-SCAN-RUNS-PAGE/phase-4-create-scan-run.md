# Phase 4 — CreateScanRun form

### Task D: Create form with two-leg submit

**Files:**
- Create: `frontend/src/features/scan-runs/CreateScanRun.tsx`
- Create: `frontend/src/features/scan-runs/CreateScanRun.test.tsx`

- [ ] **Step 1: Failing test — `CreateScanRun.test.tsx`**

Covers:
- projects-query loading / error / empty (uses the same pattern as `CreateTarget.test.tsx`)
- stubs-query loading / error / empty
- targets-query loading / error / empty for the picked project
- validation: project required, stub required, at least one target_id required
- target picker modes:
  - "all active" (default) — pre-fills with active targets for the selected project; submit body includes those ids
  - "selected only" — checkbox list renders; clearing all triggers the validation error
- happy submit ("Create scan run") → navigates to /scan-runs
- happy two-leg ("Create and start"):
  - both succeed → navigates to /scan-runs
  - create succeeds, start fails (400 illegal transition) → still navigates to /scan-runs; inline error visible; row is queued (verified via the list's MSW handler returning the queued row)
- server errors flow through `applyParsedError` (same patterns as CreateProject/CreateTarget)

- [ ] **Step 2: Implement `CreateScanRun.tsx`**

State shape:
```tsx
const [projectId, setProjectId] = useState("");
const [stubSlug, setStubSlug] = useState("");
const [pickerMode, setPickerMode] = useState<"all" | "selected">("all");
const [selectedTargetIds, setSelectedTargetIds] = useState<string[]>([]);
const [chainStart, setChainStart] = useState(false);  // which submit was clicked
const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
const [bannerError, setBannerError] = useState<string | null>(null);
const [startLegError, setStartLegError] = useState<string | null>(null);
```

Derived data:
- `useProjectsQuery()` for the project select
- `useStubsQuery()` for the stub select
- `useTargetsQuery()` — filter results client-side by `t.project === projectId && t.status === "active"`; that's the `activeTargets` set
- `targetIds = pickerMode === "all" ? activeTargets.map(t => t.id) : selectedTargetIds`

Submit pipeline:
```ts
async function onSubmit(start: boolean) {
  if (!projectId) return setFieldErrors({ project: ["project is required"] });
  if (!stubSlug) return setFieldErrors({ stub_slug: ["stub is required"] });
  if (targetIds.length === 0)
    return setFieldErrors({ target_ids: ["at least one target is required"] });

  try {
    const run = await createMutation.mutateAsync({
      project: projectId,
      stub_slug: stubSlug,
      target_ids: targetIds,
    });
    if (start) {
      try {
        await startMutation.mutateAsync(run.id);
      } catch (err) {
        // Create succeeded; preserve the queued run, surface the start
        // failure inline, and still navigate so the operator can see
        // the row + retry via the row's Start button.
        const parsed = await parseApiError(err);
        if (parsed.kind === "detail") setStartLegError(parsed.detail);
        else setStartLegError("Could not start the scan run.");
      }
    }
    navigate(ROUTES.scanRuns);
  } catch (err) {
    applyParsedError(await parseApiError(err), { setFieldErrors, setBannerError });
  }
}
```

Two submit buttons wire to `onSubmit(false)` and `onSubmit(true)` respectively; a Cancel button navigates back.

- [ ] **Step 3: Coverage 100%**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(frontend): add CreateScanRun form with two-leg submit"
```
