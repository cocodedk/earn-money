# Phase 3 — App wiring + E2E + slice ping

### Task C: Wire route + extend E2E

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.e2e.test.tsx`

- [ ] **Step 1: App.tsx — swap ComingSoon for ScanRunDetail**

```tsx
<Route path={ROUTES.scanRunDetail} element={<ScanRunDetail />} />
```

Drop the `import { ScanRunDetail } from "./features/scan-runs/ScanRunDetail"` and replace the `<ComingSoon name="Scan Run Detail" />` line.

- [ ] **Step 2: Extend E2E**

Add a fifth `it(...)` block (or extend the existing scan-runs case) that asserts: after creating a scan run, clicking "Open" on the row routes to `/scan-runs/:id` and the detail header populates.

MSW handlers needed:
- `GET /api/scan-runs/:id/` returns the same row (queued)
- Existing `/api/scan-runs/` + `/api/projects/` + `/api/stubs/` handlers stay

- [ ] **Step 3: Full coverage + build**

```bash
cd frontend && npm test -- --coverage && npm run build
```

- [ ] **Step 4: Clean build artifacts + commit**

```bash
rm -f frontend/tsconfig.node.tsbuildinfo frontend/tsconfig.tsbuildinfo frontend/vite.config.d.ts frontend/vite.config.js
rm -rf frontend/dist
git commit -m "feat(frontend): wire /scan-runs/:id to ScanRunDetail + extend E2E"
```

- [ ] **Step 5: /simplify rounds until clean**

Same loop as previous slices.

- [ ] **Step 6: Single peer ping at slice completion**

Per chat-noise-floor.

- [ ] **Step 7: Mark task #114 complete**
