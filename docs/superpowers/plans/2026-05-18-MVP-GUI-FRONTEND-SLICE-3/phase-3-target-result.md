# Phase 3 — Target result page

`/targets/:id/results` per spec `07-target-result.md`. Per-target rollup composing four sources via existing endpoints filtered by `?target=<id>`.

---

### Task H: Target detail API hook

**Files:**
- Modify: `frontend/src/features/targets/api.ts`
- Modify: `frontend/src/features/targets/api.test.tsx`

Add `useTargetDetailQuery(id)` returning `Target`.

- [ ] **Step 1: Test + implement + commit + /simplify**

---

### Task I: `TargetResult` page

**Files:**
- Create: `frontend/src/features/targets/TargetResult.tsx`
- Create: `frontend/src/features/targets/TargetResult.test.tsx`

Sections per spec:
1. **Target summary**: base_url, host, ip, status (StatusBadge), created_at.
2. **Latest scan runs for target**: uses `useScanRunsQuery({})` filtered client-side to runs that include this target — OR `useTargetsQuery + scan_run_count` — actual implementation: query `/api/scan-runs/` and filter by checking if any target_run on each run matches the target. If peer adds `/api/targets/<id>/scan-runs/`, switch to that. For slice 3, simplest: render the global scan-runs list filtered by URL (skip if backend filter not in place; verify at compose-smoke time).
3. **Findings for target**: `useFindingsQuery({target: id})`.
4. **Evidence for target**: `useEvidenceQuery({target: id})`.
5. **Events for target**: events are scoped per-scan-run, not per-target. Spec says "events for target" — interpret as "events from any scan-run that touches this target, scoped to this target_id in the event payload". Implementation: skip this section for slice 3 unless peer adds a per-target event view. Render a small `<Callout variant="info">Per-target event feed coming in slice 4.</Callout>` so the page is still complete.

Reuse `FindingsPanel` and `EvidencePanel` from slice 2's `scan-runs/detail/` directory — they're already typed and tested. Same for `TargetRunsTable`-style rendering if useful for the scan-runs section.

- [ ] **Step 1: Test** — 4 cases: target summary renders, findings panel populated by filter, evidence panel populated by filter, handles target-not-found.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Add `ROUTES.targetResult: (id) => \`/targets/${id}/results\`** to `routes.ts`.

- [ ] **Step 4: Run + commit + /simplify**
