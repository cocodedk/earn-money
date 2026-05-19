# Phase 4 — Integration

Route swaps + slice-3 e2e.

---

### Task J: Wire routes into `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`

Swap the three remaining ComingSoon placeholders (`/findings`, `/evidence`) + add the new sub-routes. Settings stays as ComingSoon.

```tsx
<Route path={ROUTES.findings} element={<FindingsList />} />
<Route path="/findings/:id" element={<FindingDetail />} />
<Route path={ROUTES.evidence} element={<EvidenceList />} />
<Route path="/evidence/:id" element={<EvidenceDetail />} />
<Route path="/targets/:id/results" element={<TargetResult />} />
<Route path={ROUTES.settings} element={<ComingSoon name="Settings" />} />
```

- [ ] **Step 1: Edit App.tsx**
- [ ] **Step 2: Run full suite + /simplify**

---

### Task K: Slice-3 e2e happy path

**Files:**
- Create: `frontend/src/App.slice3.e2e.test.tsx`

Walks: navigate to `/findings`, filter by `stub=1.1`, click a row → land on `/findings/<id>` → linked evidence visible → click an evidence row → land on `/evidence/<id>`. Plus a side path: navigate to `/targets`, click "Open target result" on a row (new row action TBD or just `<Link to={\`/targets/${id}/results\`}>` on the base_url cell), see the four sections.

- [ ] **Step 1: Test** — single long-form test like the slice-2 e2e.
- [ ] **Step 2: Run + commit + /simplify**
