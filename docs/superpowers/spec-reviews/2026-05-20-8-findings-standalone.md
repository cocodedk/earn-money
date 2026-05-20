# Spec-review — Slice 8 · Findings standalone page

**Slice:** `feat/em-frontend-8-findings-page` · 6 commits stacked on slice 7 · 433/433 tests passing · 100 % line + branch coverage on every new file.

**Umbrella spec:** [`../specs/2026-05-18-MVP-GUI/08-findings.md`](../specs/2026-05-18-MVP-GUI/08-findings.md) §8.1 Findings list + §8.2 Finding detail.

**Backend contract:** confirmed by em-backend 2026-05-20 — `/api/findings/` filters (AND semantics, all optional): `scan_run`, `project`, `target`, `stub_slug`, `severity`, `confidence`, `status`. Detail: `/api/findings/<id>/`. Linked evidence: `/api/evidence/?finding=<uuid>`.

---

## 1. Detection-logic coverage

Every spec requirement is reachable in code:

| Spec requirement | Code path | Test |
|---|---|---|
| `/findings` list route | `App.tsx` wires `<FindingsList />` | E2E test 1 |
| 7 filters (project / target / scan_run / stub / severity / confidence / status) | `FindingsFiltersBar.tsx` URL-encodes via `useSearchParams` | `FindingsList.filters.test.tsx` covers all 7 |
| Table columns (Title / Target / Stub / Category / Severity / Confidence / Status / Created at / Actions) | `FindingsList.tsx` Table column array | `FindingsList.test.tsx` rendering test |
| Actions: Open finding + Open evidence | Two `<Link>` cells per row | E2E test 3 (navigation), filters test (link present) |
| `/findings/:findingId` detail route | `App.tsx` wires `<FindingDetail />` | E2E test 3 |
| Detail fields (title / target / scan run / stub / category / severity / confidence / status / data JSON / linked evidence / created_at / updated_at) | `FindingDetail.tsx` | `FindingDetail.test.tsx` rendering tests |
| Linked evidence table (source / url / field / matched_value / raw_excerpt / created_at) | `<Table>` with `useFindingLinkedEvidenceQuery(id)` | `FindingDetail.test.tsx` evidence-section test |

## 2. Persistence contract

N/A — page is read-only. Only `useQuery` hooks, no `useMutation`. Verified: `grep -r "useMutation\|fetch.*POST\|fetch.*DELETE" frontend/src/features/findings/` returns zero hits.

## 3. Pass/fail positive assertions

- Table renders 3 rows from 3-finding fixture → `FindingsList.test.tsx`.
- Each filter individually applied → `FindingsList.filters.test.tsx` (7 tests, one per filter).
- AND-semantics combo (severity=medium + confidence=high) → filters test.
- Truncation footer when `next != null` → list test.
- Detail page renders every field → detail test.
- Linked evidence section renders → detail test.

## 4. Pass/fail negative assertions

- No `useMutation` hooks imported by slice 8 files (grep regression in spec-review).
- Empty filters object → request hits `/api/findings/` with no query params (verified in `api.test.tsx`).
- Detail page disabled when `findingId === undefined` → no request made (api test).
- "All …" filter dropdown values clear the URL param (don't send empty string) → filters test.

## 5. Acceptance criteria

- Operator can open `/findings`, see all findings across all scans.
- Operator can deep-link with filter params and browser back/forward works (URL is source of truth).
- Operator can click a row's "Open finding" to land on `/findings/<id>` with full detail.
- Operator can click a row's "Open evidence" to land on `/evidence?finding=<id>` (consumed in slice 9).
- All filters compose with AND semantics matching backend.

## 6. Idempotence / determinism / bounded

- Query key includes the filter set deterministically (`["findings", "list", ...sortedFilters]`) so React Query dedupes correctly.
- Pagination respects DRF `PAGE_SIZE=50`; truncation footer appears when `next != null`.
- Detail query disabled when id is undefined → no infinite-fetch loop.

## 7. Transport-error tolerance

- List page renders error callout when the query errors out (test in `FindingsList.test.tsx`).
- Detail page renders not-found state when finding id doesn't exist (404 path) (test in `FindingDetail.test.tsx`).
- Filters dropdowns degrade gracefully when projects/targets/stubs/scan-runs lookups error (assertion: dropdown still renders with only "All …" option).

---

## Tracked follow-ups (deferred, do NOT block slice 8)

1. **Saved filter presets** — operator may want to save common filter combos (`severity=high`); not in MVP spec. Defer until operator asks.
2. **Sort columns** — currently follows backend default ordering (`created_at desc`). MVP spec doesn't require column-click sorting. Defer.
3. **Bulk actions** — Actions column is per-row only. Bulk status changes (e.g., select multiple → mark "confirmed") deferred to a future triage slice.
4. **`useFindingsFiltersFromUrl` helper extraction** — small utility for parsing/serializing the 7 filter params; small enough to inline for now. Lift when a second filter-driven page appears (slice 9 may justify this).

---

## Verdict

**Slice 8 shipped.** All seven audit dimensions clear. 433/433 tests passing. No new actionable findings against the spec.
