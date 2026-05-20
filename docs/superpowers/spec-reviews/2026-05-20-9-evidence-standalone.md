# Spec-review — Slice 9 · Evidence standalone page

**Slice:** `feat/em-frontend-9-evidence-page` · 5 commits stacked on slice 8 · 460/460 tests passing · 100 % line + branch coverage on every new file.

**Umbrella spec:** [`../specs/2026-05-18-MVP-GUI/09-evidence.md`](../specs/2026-05-18-MVP-GUI/09-evidence.md) §9.1 Evidence list + §9.2 Evidence detail.

**Backend contract:** confirmed against em-backend slice — `/api/evidence/` filters (AND semantics, all optional): `project`, `target`, `scan_run`, `finding`, `source`. Detail: `/api/evidence/<id>/`. Read-only — no write endpoints touched by this slice.

---

## 1. Detection-logic coverage

Every spec requirement is reachable in code:

| Spec requirement | Code path | Test |
|---|---|---|
| `/evidence` list route | `App.tsx` wires `<EvidenceList />` | E2E test |
| 5 filters (project / target / scan_run / finding / source) | `EvidenceFiltersBar.tsx` URL-encodes via `useSearchParams`; `FILTER_PARAM_KEYS` is the canonical set | `EvidenceList.filters.test.tsx` covers every filter shape (select + text + clear) |
| Table columns (Target / Source / URL / Method / Field / Matched value / Created at / Actions) | `EvidenceList.tsx` Table column array | `EvidenceList.test.tsx` rendering test |
| Action: Open evidence | `<Link>` cell per row → `/evidence/<id>` | E2E test (navigation) + `EvidenceList.test.tsx` link-presence assertion |
| Bonus: Open finding when `finding != null` | second `<Link>` cell with `evidence-finding-link-<id>` testid | `EvidenceList.test.tsx` finding-link presence + null-finding omission tests |
| `/evidence/:evidenceId` detail route | `App.tsx` wires `<EvidenceDetail />` | E2E test |
| Detail fields (target / scan_run / finding-if-linked / source / url / method / field / matched_value / raw_excerpt / content_hash / data JSON / created_at) | `EvidenceDetail.tsx` MetaList + raw-excerpt + data sections | `EvidenceDetail.test.tsx` rendering test asserts every section |
| `raw_excerpt` must be visible (§9.2 important) | dedicated `<section data-testid="evidence-raw-excerpt-section">` with `<pre>` | `EvidenceDetail.test.tsx` excerpt-text assertion |

## 2. Persistence contract

N/A — page is read-only. Only `useQuery` hooks, no `useMutation`. Verified: `grep -r "useMutation\|fetch.*POST\|fetch.*DELETE" frontend/src/features/evidence/` returns zero hits.

## 3. Pass/fail positive assertions

- Table renders N rows from an N-evidence fixture → `EvidenceList.test.tsx`.
- Each filter applied (URL → query string round-trip) → `EvidenceList.filters.test.tsx` (project, target, scan_run, source).
- Detail page renders every field (target/scan_run/finding/source/url/method/field/matched_value/raw_excerpt/data) → `EvidenceDetail.test.tsx`.
- Truncation footer when `next != null` → list test.
- Open-finding cross-link only when `finding != null` → list test (positive + negative).
- E2E flow: list → filter → detail navigation succeeds → `App.e2e.evidence.test.tsx`.

## 4. Pass/fail negative assertions

- No `useMutation` hooks imported by slice 9 files (grep regression).
- Empty filters object → request hits `/api/evidence/` with no query string (asserted in `api.test.tsx`: empty filters yield `""`).
- Detail query disabled when `evidenceId === undefined` → no request fires (api test).
- "All …" filter dropdown values clear the URL param (don't send empty string) → filters test.
- Open-finding link omitted when `evidence.finding === null` → list test.
- `raw_excerpt = null` renders em-dash, not the literal string `null` → detail test.

## 5. Acceptance criteria

- Operator can open `/evidence`, see every evidence record across all scans.
- Operator can deep-link with filter params (`?project=…&finding=…`) and browser back/forward works (URL is source of truth).
- Operator can click a row's "Open evidence" to land on `/evidence/<id>` with full detail including raw excerpt.
- Operator can click "Open finding" on a row whose evidence is linked to a finding — bridges to slice 8.
- All filters compose with AND semantics matching backend.

## 6. Idempotence / determinism / bounded

- Query key includes the filter set in stable order (`["evidence", "list", ...flat(FILTER_KEYS)]`) so React Query dedupes — `evidenceListKey({source:"x",project:"p"})` equals `evidenceListKey({project:"p",source:"x"})` (api test).
- `buildQueryString` walks `FILTER_KEYS` in canonical order — URL encoding is deterministic regardless of caller key order.
- Pagination respects DRF `PAGE_SIZE`; truncation footer appears when `next != null`.
- Detail query disabled when id is undefined → no infinite-fetch loop.

## 7. Transport-error tolerance

- List page renders error callout when the query 5xx's (`EvidenceList.test.tsx`).
- Detail page renders 404 "Not found" state (`EvidenceDetail.test.tsx`).
- Detail page renders "Could not load evidence." on non-404 errors (`EvidenceDetail.test.tsx`).
- Filter dropdowns degrade gracefully when projects/targets/scan-runs/findings lookups error — the parent feature pages already test this and the same hooks are reused here, no slice-9-specific path.

---

## Tracked follow-ups (deferred, do NOT block slice 9)

1. **Finding-dropdown scalability** — the `Finding` filter dropdown loads `useFindingsListQuery({})` which paginates at 50 entries. Once a project carries thousands of findings, the dropdown will only see the first page. Replace with a typeahead / async-search input when this becomes painful. Same shape as the scan-run dropdown which has the same latent issue.
2. **raw_excerpt rendering** — currently rendered inside `<pre>` with no syntax highlighting, no line numbers, no copy button. MVP spec only says "should be visible". Defer richer rendering (HTTP header colorization, JSON pretty-print, request/response split) until operator asks.
3. **`data` JSON rendering** — rendered via `JSON.stringify(data, null, 2)` inside `<pre>`. No collapsible tree, no diff against another evidence row. Sufficient for MVP; revisit when triage workflows need it.
4. **Saved filter presets** — same gap as slice 8. Operator may want to save "all CSP findings on prod target" combos. Defer until asked.
5. **`useEvidenceFiltersFromUrl` helper extraction** — `readFilters(params)` in `EvidenceList.tsx` is a clone of the equivalent in `FindingsList.tsx`. Small enough to keep inline; lift into `lib/` if a third filter-driven page appears.

---

## Verdict

**Slice 9 shipped.** All seven audit dimensions clear. 460/460 tests passing. No new actionable findings against the spec.
