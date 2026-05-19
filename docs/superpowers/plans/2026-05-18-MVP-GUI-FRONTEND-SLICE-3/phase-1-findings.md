# Phase 1 — Findings UI

`<FiltersBar>` primitive, `/findings` list with the 7 filters, `/findings/:id` detail.

---

### Task C: `<FiltersBar>` primitive

A generic row of filter dropdowns. Takes `filters: FilterDef[]` + `values: Record<string,string>` + `onChange(key, value)`.

**Files:**
- Create: `frontend/src/components/FiltersBar/FiltersBar.tsx`
- Create: `frontend/src/components/FiltersBar/FiltersBar.module.css`
- Create: `frontend/src/components/FiltersBar/FiltersBar.test.tsx`
- Create: `frontend/src/components/FiltersBar/index.ts`

```ts
export type FilterOption = { value: string; label: string };
export type FilterDef = {
  key: string;
  label: string;
  options: FilterOption[];
};
export type FiltersBarProps = {
  filters: FilterDef[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
};
```

- [ ] **Step 1: Test** — 3 cases:
  1. Renders each filter as a labelled `<select>` with `option`s including a leading "All" sentinel with value `""`.
  2. `values[key]` is reflected as the selected option.
  3. Changing a select fires `onChange(key, newValue)`.

- [ ] **Step 2: Implement** — wrap in a `<div className={styles.bar}>` with a horizontal flex layout; each filter is a `<label className={styles.filter}>` with the select inside.

- [ ] **Step 3: Run + commit + /simplify**

---

### Task D: `FindingsList` page

**Files:**
- Create: `frontend/src/features/findings/FindingsList.tsx`
- Create: `frontend/src/features/findings/FindingsList.test.tsx`

The filter dropdowns are populated as follows:
- **project**: from `useProjectsQuery()` results, mapped to `{value: id, label: name}`.
- **target**: from `useTargetsQuery(currentProjectId)` — only active targets of the current project (if a project is selected). If no current project, just shows "All".
- **scan_run**: from `useScanRunsQuery({project: currentProjectId})` mapped to `{value: id, label: id.slice(0, 8)}`.
- **stub**: from `useStubsQuery()` mapped to `{value: slug, label: \`${slug} — ${title}\`}`.
- **severity**: hard-coded enum from `types/api.ts`: `info | low | medium | high | critical`.
- **confidence**: hard-coded enum: `low | medium | high`.
- **status**: hard-coded enum: `candidate | confirmed | rejected | stale`.

Filter values are stored as URL search params (`/findings?stub=1.1&severity=high`) so the operator can share/bookmark filtered views. Use `useSearchParams` from `react-router-dom`.

Table columns (per spec `08-findings.md`): Title (link to detail), Target (UUID prefix), Stub, Category, SeverityBadge, Confidence, Status, Created at.

- [ ] **Step 1: Test** — 6 cases: loading skeleton, empty state, populated rows render expected fields, error retry, filter change updates the URL + refetches, title link goes to `/findings/<id>`.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Run + commit + /simplify**

---

### Task E: `FindingDetail` page

**Files:**
- Create: `frontend/src/features/findings/FindingDetail.tsx`
- Create: `frontend/src/features/findings/FindingDetail.test.tsx`

Sections per `08-findings.md`:
- Title
- Linked metadata: target, scan run, stub, category, severity (badge), confidence, status, created/updated
- `data` JSON block (rendered in a `<pre>` font-mono)
- Linked evidence table — uses `useEvidenceQuery({finding: id})`. Columns: source, url, field, matched value, raw_excerpt (truncated), created_at. Empty state "No linked evidence."

- [ ] **Step 1: Test** — 4 cases: renders finding fields, renders linked evidence list, handles not-found 404, handles loading state.

- [ ] **Step 2: Implement.** Reuse `<PageHeader>`, `<SeverityBadge>`, `<Table>` from slice 1/2.

- [ ] **Step 3: Run + commit + /simplify**

Add `/findings/:id` to `ROUTES` (`findingDetail: (id) => \`/findings/${id}\``) — defer wiring to App.tsx until Phase 4.
