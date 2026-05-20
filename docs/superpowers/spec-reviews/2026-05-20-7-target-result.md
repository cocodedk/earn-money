# Spec-review — Slice 7 Target Result page

**Slice:** `feat/em-frontend-7-target-result` · 5 commits · 404 tests passing · 100 % line + branch coverage on every new file.

**Umbrella spec:** [`../specs/2026-05-18-MVP-GUI/`](../specs/2026-05-18-MVP-GUI/) — Target detail / result page composing target-scoped scan-runs, findings, evidence, and events.

**Phase commits (source of truth):**

1. `313acf3` — target-scoped hooks (`useTargetQuery`, `useTargetScanRunsQuery`, `useTargetFindingsQuery`, `useTargetEvidenceQuery`, `useTargetEventsQuery`).
2. `3aefd87` — /simplify on hooks: collapsed `useTargetChildQuery<T>(targetId, child)` generic.
3. `6943798` — `TargetResult.tsx` page composing all 4 child sections under `DetailPageGuard`.
4. `68a8c68` — /simplify on page: extracted `TargetSection<T>` primitive + `format.ts` helpers; split each panel into its own ≤ 40-line file under `TargetResult/`.
5. `26154a5` — Phase 3: `TargetsList` "Open results" `ButtonLink` per row + `App.e2e.target-result.test.tsx` clicking through end-to-end.

Audit dimensions are the seven from `CLAUDE.md` §Commit hygiene → "After implementing a cookbook stub, run the spec-review pass before marking it done."

---

## 1. Detection-logic coverage

Every section the slice ships is reachable in production code with at least one positive integration test plus a hook-level unit test:

| Section / signal | Production code | Test |
|---|---|---|
| Target summary header (id, base_url) | `TargetResult.tsx` `DetailBody` | `TargetResult.test.tsx` test 1 asserts `/Target · 22222222 · https:\/\/dvwa\.cocode\.dk/` |
| Project name resolution | `useProjectNameLookup` in `DetailBody` | `TargetResult.test.tsx` test 1 asserts `"Local Lab"` |
| IP / status / created_at meta rows | `MetaList` rows in `DetailBody` | `TargetResult.test.tsx` test 1 (`"1.2.3.4"`); `errors-edges.test.tsx` test 2 (`null` ip → `—`) |
| Scan-runs section (latest runs for target) | `TargetScanRunsTable.tsx` → `useTargetScanRunsQuery` (`/api/scan-runs/?target=<id>`) | `api.scan-runs.test.tsx` test 1; `TargetResult.test.tsx` test 1 asserts `target-scan-runs-section` + 2 row testids |
| Findings section | `TargetFindingsPanel.tsx` → `useTargetFindingsQuery` (`/api/findings/?target=<id>`) | `api.findings.test.tsx` test 1; `TargetResult.test.tsx` test 1 asserts 3 finding rows |
| Evidence section | `TargetEvidencePanel.tsx` → `useTargetEvidenceQuery` (`/api/evidence/?target=<id>`) | `api.evidence.test.tsx`; `TargetResult.test.tsx` test 1 asserts 5 evidence rows |
| Events section | `TargetEventsTable.tsx` → `useTargetEventsQuery` (`/api/events/?target=<id>`) | `api.events.test.tsx`; `TargetResult.test.tsx` test 1 asserts 4 event rows |
| Cross-page navigation (list → detail) | `TargetsList.tsx` "Open results" `ButtonLink` → `targetResultPath(id)` | `TargetsList.test.tsx` "renders an Open results link…"; `App.e2e.target-result.test.tsx` clicks through |
| Not-found / load-error guards | `DetailPageGuard` wraps `useTargetQuery` | covered by `DetailPageGuard` tests + reused by `ScanRunDetail` |

## 2. Persistence contract

**N/A — page is read-only.** Verified explicitly:

- All five new target hooks in `api.ts` are `useQuery` only — no new `useMutation`.
- The pre-existing `useCreateTargetMutation` (line 32 of `api.ts`) is **not** imported anywhere in `TargetResult.tsx`, `TargetResult/*.tsx`, or any of the four new panel files. `grep useMutation` against the slice 7 production tree returns only that one pre-existing definition, untouched.
- All four child hooks issue `GET /api/<child>/?target=<id>` — verified by `api.{scan-runs,findings,evidence,events}.test.tsx` (each test instantiates the hook and reads `request.url`'s `target` param).
- The page renders no `<form>`, no `<button onClick>` that mutates, no `useNavigate(...).back`-style side effects.

## 3. Pass/fail positive assertions

Every section has at least one positive render test:

- **Header + meta:** `TargetResult.test.tsx` test 1 — title, project, IP, status, created_at.
- **All 4 child sections rendered:** `TargetResult.test.tsx` test 1 — `target-scan-runs-section`, `target-findings-section`, `target-evidence-section`, `target-events-section` all queried via `findByTestId`.
- **Row counts:** `TargetResult.test.tsx` test 1 — 2 scan-run rows, 3 finding rows, 5 evidence rows, 4 event rows.
- **Truncation hint:** `TargetResult.errors-edges.test.tsx` test 3 — `next != null` produces `*-truncation` for all four sections.
- **E2E click-through:** `App.e2e.target-result.test.tsx` test 1 — render `<App />` at `/targets`, click `Open results`, assert all 5 testid sections + row counts.
- **List → detail link:** `TargetsList.test.tsx` "renders an Open results link…" — `href="/targets/t-1/results"`.

## 4. Pass/fail negative assertions

The "must not" rules are exercised by regression tests:

- **No mutating HTTP from any child hook** — each `api.{scan-runs,findings,evidence,events}.test.tsx` registers a `GET`-only MSW handler; any `POST`/`PUT`/`PATCH`/`DELETE` would 404 (MSW default).
- **No useMutation in TargetResult tree** — grep-verified; only `useCreateTargetMutation` exists in `api.ts`, and it's not imported by any TargetResult file.
- **Hooks disabled until id is truthy** — `api.findings.test.tsx` test 2 ("disabled when targetId is undefined") + `api.single.test.tsx` test 2 ("is disabled when id is undefined") assert `calls === 0` on `undefined` id; same pattern applies to all four child hooks via the shared `useTargetChildQuery` enable guard.
- **No section renders when target itself fails to load** — `DetailPageGuard` short-circuits before `DetailBody` mounts; reused contract from `ScanRunDetail`.
- **Confidence blank string does NOT explode** — `TargetResult.errors-edges.test.tsx` test 2 passes `confidence: ""` and asserts `—` falls back via the `f.confidence || "—"` guard in `TargetFindingsPanel`.

## 5. Acceptance criteria

All operator-facing acceptance items:

- ✅ Operator navigates from `/targets` to `/targets/:id/results` via the new "Open results" `ButtonLink` (`App.e2e.target-result.test.tsx`).
- ✅ All 5 visible regions render with rows from a populated fixture: header, scan-runs, findings, evidence, events.
- ✅ Empty states render per section when `count === 0` (`TargetResult.test.tsx` test 2 — `target-{scan-runs,findings,evidence,events}-empty` testids).
- ✅ 100 % line + branch + function coverage on every new production file (`727/727` stmts, `357/357` branches, `333/333` functions per `npm test -- --coverage` at HEAD).
- ✅ All new and modified files ≤ 200 lines:
  - `TargetResult.tsx` 61 · `TargetSection.tsx` 61 · `TargetScanRunsTable.tsx` 37 · `TargetEventsTable.tsx` 37 · `TargetFindingsPanel.tsx` 32 · `TargetEvidencePanel.tsx` 32 · `format.ts` 16 · `testkit.tsx` 44 · `api.ts` 68 · `App.e2e.target-result.test.tsx` 103 · `TargetsList.tsx` 78.
- ✅ Conventional Commits across all 5 commits (test/feat/refactor scopes correct).

## 6. Idempotence / determinism / bounded

- **Bounded results:** all four child hooks use the same DRF `Paginated<T>` envelope; `TargetSection<T>` renders only `query.data.results` and surfaces a `*-truncation` hint when `next !== null` (per `TargetResult.errors-edges.test.tsx` test 3).
- **Deterministic ordering:** rows render in server-emitted order — no client-side sort. Verified by row-id assertions in `TargetResult.test.tsx` test 1 (`findAllByTestId(/^target-finding-row-/)`).
- **No unbounded growth:** read-only page; React Query holds one cached page per `[...TARGETS_KEY, id, child]` key.
- **Dedupe / refetch idempotence:** delegated to React Query keyed cache — identical hook calls share state across panels.

## 7. Transport-error tolerance

Each child panel surfaces its own error state without sinking the page:

- **Per-section error callout:** `TargetSection<T>` returns a `<Callout variant="error">{copy.errorMessage}</Callout>` when `query.isError`. Verified by `TargetResult.errors-edges.test.tsx` test 1 — all 4 endpoints `HttpResponse.error()`, page renders 4 distinct callouts (`/Could not load scan runs|findings|evidence|events/`).
- **Null-tolerant cell rendering:** `dash()` helper covers nullable `Evidence` fields (`url`, `method`, `field`, `matched_value`); `fmtDateTime()` covers nullable `ScanRun.started_at` / `finished_at`. Both exercised by `TargetResult.errors-edges.test.tsx` test 2.
- **Cross-section isolation:** error in one section does NOT prevent the other three from rendering — each panel owns its own `useQuery` instance.
- **Target itself fails to load:** `DetailPageGuard` renders the standard error/not-found views; reused contract from `ScanRunDetail`.

---

## Deferrals & follow-ups (recorded — do NOT block slice 7)

Picked up from the 6D spec-review and still open at slice 7 close:

1. **`format.ts` extraction to a project-wide util** — `fmtDate` / `fmtDateTime` / `dash` now exist in *both* `TargetResult/format.ts` *and* analogous inline forms in `ScanRun*Panel.tsx`. Lift to a shared `lib/format.ts` (or `components/format/`) in a future cleanup slice. Tracked since 6D #2.
2. **`useTargetChildQuery<T>` ↔ `useScanRunChildQuery<T>` consolidation** — two parallel generics now exist (one in `scan-runs/api.ts`, one in `targets/api.ts`). A single `useResourceChildQuery<T>(parentKey, parentId, child)` could collapse both. Defer until a third parent appears. Tracked since 6D #1.
3. **Truncation UX** — "Showing first N of M <noun>" is a flat hint; no "Load more" or pagination control. Out of scope for slice 7; defer until operator feedback drives it.
4. **List → detail link could be a row-click affordance** — currently a per-row `ButtonLink` in an Actions column. Matches `ScanRunsList` precedent; if the operator wants whole-row click navigation later, lift to `Table` rowProps.

## Verdict

**Slice 7 shipped.** All seven audit dimensions cleared. 404/404 tests passing on `feat/em-frontend-7-target-result` (402 baseline + 1 `TargetsList` row-link test + 1 E2E). 100 % coverage on the entire production tree. No new actionable findings against the slice's scope.
