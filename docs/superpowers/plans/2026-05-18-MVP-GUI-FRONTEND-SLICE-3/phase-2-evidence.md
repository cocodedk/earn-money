# Phase 2 — Evidence UI

`/evidence` list with 5 filters, `/evidence/:id` detail.

---

### Task F: `EvidenceList` page

**Files:**
- Create: `frontend/src/features/evidence/EvidenceList.tsx`
- Create: `frontend/src/features/evidence/EvidenceList.test.tsx`

Filter dropdowns per `09-evidence.md`: project, target, scan_run, finding, source.
- **project**, **target**, **scan_run**, **finding**: populated like FindingsList.
- **source**: free-text source kinds (`header.X-Powered-By`, `body.html`, `cookie.PHPSESSID`, etc.). Since there's no closed enum, render a `<input type="text">` rather than a `<select>`. To keep `<FiltersBar>` simple, the `FilterDef` for `source` uses `options: []` and the component renders a text input when options is empty. (Update `<FiltersBar>` from Phase 1 Task C to support this.)

Filter values stored as URL search params via `useSearchParams`.

Table columns per spec: Source, Target (UUID prefix), URL, Method, Field, Matched value (font-mono), Created at.

- [ ] **Step 1: Update `<FiltersBar>`** to render a `<input type="text">` when a FilterDef has `options.length === 0`. Add a test in Phase 1 Task C's test file: "renders text input when options is empty; onChange fires on debounced typing".

- [ ] **Step 2: Test EvidenceList** — same 6-case shape as FindingsList.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run + commit + /simplify**

---

### Task G: `EvidenceDetail` page

**Files:**
- Create: `frontend/src/features/evidence/EvidenceDetail.tsx`
- Create: `frontend/src/features/evidence/EvidenceDetail.test.tsx`

Per spec `09-evidence.md`:
- target, scan run, finding (if linked → link to `/findings/<id>`), source, url, method, field, matched_value, raw_excerpt (visible in font-mono block, no need for full raw response), content_hash, data JSON, created_at.

- [ ] **Step 1: Test** — 4 cases: renders all spec fields, renders "—" for nullable fields, handles 404, renders finding link only when finding is non-null.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Run + commit + /simplify**
