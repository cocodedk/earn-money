# Phase 5 — App wiring + E2E + slice ping

### Task E: Wire routes + extend E2E

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.e2e.test.tsx`

- [ ] **Step 1: App.tsx**

Swap `<ComingSoon name="Scan Runs" />` for the real list. Add the `/scan-runs/new` route. Leave `/scan-runs/:id` as ComingSoon for slice 06.

```tsx
<Route path={ROUTES.scanRuns} element={<ScanRunsList />} />
<Route path={ROUTES.scanRunsNew} element={<CreateScanRun />} />
<Route path="/scan-runs/:id" element={<ComingSoon name="Scan Run Detail" />} />
```

- [ ] **Step 2: Extend E2E**

Add a fourth `it(...)` to `App.e2e.test.tsx`:
1. Create a project (uses the existing project handlers + `Create project` path)
2. Create a target (handlers + `Create target`)
3. Navigate `/scan-runs/new`
4. Pick project, pick stub "1.1", default-pick "all active"
5. Click "Create and start"
6. Land on `/scan-runs`; row shows queued or running state
7. Click Start (if queued); row flips to running

MSW handlers:
- `POST /api/scan-runs/` returns a queued ScanRun
- `POST /api/scan-runs/<id>/start/` returns a running ScanRun
- `GET /api/scan-runs/` returns the current state (driven by closure-local state in the handler so the refetch reflects the start)

- [ ] **Step 3: Coverage + build green**

```bash
cd frontend && npm test -- --coverage && npm run build
```

- [ ] **Step 4: Clean build artifacts + commit**

- [ ] **Step 5: /simplify rounds until clean**

Same loop as Targets/Stubs slices: run /simplify, action in-scope findings, defer out-of-scope as tasks, repeat until three reviewers report clean.

- [ ] **Step 6: Single peer ping**

`chat_message_agent` to `agent-em-backend`: "Scan Runs slice 1 done on refactor/archive-v1. Commits ee1d8d2..<final>. 100% coverage; build green. /simplify clean. Open button routes to /scan-runs/:id which stays ComingSoon for slice 06. Thanks for the findings_count annotation."

- [ ] **Step 7: chat_notify operator with SHA list for push auth (per [Notify before push] rule)**

- [ ] **Step 8: Mark task #112 complete**
