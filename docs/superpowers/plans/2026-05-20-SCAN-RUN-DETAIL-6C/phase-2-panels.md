# Phase 2 — Panel components

**Goal:** Ship `ScanRunFindingsPanel` and `ScanRunEvidencePanel` — both read-only tables, scan-run-scoped, taking `(scanRunId, livePolling)` and rendering loading / empty / error / table / truncation states. Not yet wired into `ScanRunDetail` (that's Phase 3).

**Reference patterns:** `frontend/src/features/scan-runs/ScanRunTargetsTable.tsx` (64 lines) is the canonical template. Both new panels mirror its structure exactly: raw `<table>`, inline `fmt` helper, `<Callout>` for errors, truncation footer with testid, per-row `data-testid` for transition tests.

**Parallelism note for the controller:** Tasks 6 and 7 share zero state (different files, different fixtures, different MSW routes — both already shipped in Phase 1). The subagent-driven-development controller MAY dispatch both implementer subagents in parallel. Merge order doesn't matter. Spec review and code-quality review of each task are independent.

**Per-row testid convention:**
- Findings panel: `data-testid="finding-row-{id}"`
- Evidence panel: `data-testid="evidence-row-{id}"`

**Truncation footer testid:**
- Findings panel: `data-testid="findings-truncation"`
- Evidence panel: `data-testid="evidence-truncation"`

---

### Task 6: `ScanRunFindingsPanel` component

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunFindingsPanel.tsx`
- Test: `frontend/src/features/scan-runs/ScanRunFindingsPanel.test.tsx`

**Columns:** Title, Target (first 8 chars, mono), Category, Severity (plain text), Confidence (plain text), Status (plain text), Created (date only).

**Decision note on badge rendering:** `frontend/src/features/scan-runs/StatusBadge.tsx` is a typed `ScanRunStatus` wrapper around the generic `frontend/src/components/StatusBadge/StatusBadge.tsx` and ships a `STATUS_PALETTE: Record<ScanRunStatus, string>` — passing a `Severity` (`"low"`/`"high"`/etc.) or `FindingStatus` (`"candidate"`/etc.) would render uncoloured and break the typed contract. 6C renders severity/confidence/status as plain text (`<td>{f.severity}</td>`) — no badge. Colour-coded `SeverityBadge` (mirroring slice-3's component) and a typed `FindingStatusBadge` can ship as a follow-up if the operator wants visual hierarchy; not needed to satisfy the umbrella spec which lists columns without specifying badge styling.

- [ ] **Step 1: Write the failing test** — `ScanRunFindingsPanel.test.tsx`

Use `renderWithProviders` from `frontend/src/test/renderWithProviders.tsx` for component tests, and `withPaginated()` from `frontend/src/test/helpers.tsx:13` for default 0-row server stubs. Mirror the pattern in `frontend/src/features/scan-runs/ScanRunTargetsTable.test.tsx`.

**Full test checklist — write each test, do not collapse to "follows same shape":**

- [ ] T1. `renders heading with count` — server returns 3 findings, assert `screen.findByText(/Findings \(3\)/)` resolves.
- [ ] T2. `renders all seven column headers in order` — assert `Title`, `Target`, `Category`, `Severity`, `Confidence`, `Status`, `Created` text present in `<th>` elements.
- [ ] T3. `renders one row per finding` — server returns 3 findings, assert `screen.findAllByTestId(/^finding-row-/)` returns 3 elements.
- [ ] T4. `each row has data-testid="finding-row-{id}"` — assert `screen.getByTestId("finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa")` for a specific fixture.
- [ ] T5. `renders loading state with data-testid="findings-loading"` — set up a `delay(2000)` server response, assert `screen.findByTestId("findings-loading")` resolves before the response arrives.
- [ ] T6. `renders Callout when query errors` — server returns `HttpResponse.error()`, assert `screen.findByText(/Could not load findings/)` resolves.
- [ ] T7. `renders empty state with data-testid="findings-empty"` — server returns `{count: 0, next: null, previous: null, results: []}`, assert `screen.findByTestId("findings-empty")` resolves AND heading reads "Findings (0)".
- [ ] T8. `formats created_at to YYYY-MM-DD` — fixture `created_at: "2026-05-20T08:00:00Z"`, assert cell shows `"2026-05-20"` exactly (use `within(row).getByText("2026-05-20")`).
- [ ] T9. `renders truncation footer when next !== null` — server returns `{count: 75, next: "/api/findings/?scan_run=...&page=2", previous: null, results: [makeFinding({id: "ffffffff-..."})]}` (1 row in `results`), assert `screen.findByTestId("findings-truncation")` resolves AND its `toHaveTextContent("Showing first 1 of 75 findings")` matches (text mirrors 6B `ScanRunTargetsTable.tsx:59` exactly — no hardcoded 50).
- [ ] T10. `does NOT render truncation footer when next === null` — assert `screen.queryByTestId("findings-truncation")` returns `null`.
- [ ] T11. `truncates target UUID to first 8 chars in mono` — fixture `target: "22222222-2222-..."`, assert the cell shows `<code>22222222</code>` (use `within(row).getByText("22222222")` and verify the parent is a `<code>` element).
- [ ] T12. `renders severity/confidence/status as plain text` — fixture `severity: "high", confidence: "medium", status: "candidate"`, assert each text appears as plain text inside the row via `within(row).getByText("high")` / `"medium"` / `"candidate"` (no `<span data-testid="status-...">` wrapper — those would only appear if `StatusBadge` were used).

Sample test scaffold (write all 12 in this style):

```tsx
import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withPaginated } from "../../test/helpers";
import { ScanRunFindingsPanel } from "./ScanRunFindingsPanel";
import { makeFinding } from "./__fixtures__/finding";

const SCAN_RUN_ID = "11111111-1111-1111-1111-111111111111";

describe("ScanRunFindingsPanel", () => {
  it("renders heading with count", async () => {
    withPaginated("/api/findings/", [
      makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa", title: "A" }),
      makeFinding({ id: "ffffffff-bbbb-bbbb-bbbb-bbbbbbbbbbbb", title: "B" }),
      makeFinding({ id: "ffffffff-cccc-cccc-cccc-cccccccccccc", title: "C" }),
    ]);
    renderWithProviders(
      <ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />,
    );
    expect(await screen.findByText(/Findings \(3\)/)).toBeInTheDocument();
  });

  // ... write T2 through T12 each as its own `it(...)` block, one observable
  // per test. For T6 (error), use server.use(msw.get("/api/findings/", () =>
  // HttpResponse.error())) instead of withPaginated.
});
```

Run: `npm test -C frontend -- ScanRunFindingsPanel.test.tsx --run`
Expected: FAIL with "Cannot find module './ScanRunFindingsPanel'"

- [ ] **Step 2: Implement** — `ScanRunFindingsPanel.tsx` (target ~70 lines, hard cap 200)

```tsx
import { Callout } from "../../components/Callout";
import { useScanRunFindingsQuery } from "./api";
import type { Finding } from "../../types/api";

type Props = { scanRunId: string; livePolling: boolean };

function fmt(ts: string | null): string {
  return ts ? ts.slice(0, 10) : "—";
}

export function ScanRunFindingsPanel({ scanRunId, livePolling }: Props) {
  const query = useScanRunFindingsQuery(scanRunId, { livePolling });

  if (query.isError) {
    return <Callout variant="error">Could not load findings.</Callout>;
  }
  if (!query.data) {
    return <div data-testid="findings-loading">Loading findings…</div>;
  }
  const { results, count, next } = query.data;
  if (count === 0) {
    return (
      <section>
        <h3>Findings (0)</h3>
        <p data-testid="findings-empty">No findings yet for this run.</p>
      </section>
    );
  }

  return (
    <section>
      <h3>Findings ({count})</h3>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Target</th>
            <th>Category</th>
            <th>Severity</th>
            <th>Confidence</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {results.map((f: Finding) => (
            <tr key={f.id} data-testid={`finding-row-${f.id}`}>
              <td>{f.title}</td>
              <td><code>{f.target.slice(0, 8)}</code></td>
              <td>{f.category}</td>
              <td>{f.severity}</td>
              <td>{f.confidence}</td>
              <td>{f.status}</td>
              <td>{fmt(f.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {next !== null && (
        <p data-testid="findings-truncation">
          Showing first {results.length} of {count} findings
        </p>
      )}
    </section>
  );
}
```

Note on guards: this mirrors shipped 6B `ScanRunTargetsTable.tsx` exactly — `query.isError` first, then `!query.data` (covers both `isLoading` AND the no-cached-data terminal-flush race), then empty state on `count === 0`. No `isLoading` check is needed because `!query.data` subsumes it.

- [ ] **Step 3: Run tests**

Run: `npm test -C frontend -- ScanRunFindingsPanel.test.tsx --run`
Expected: PASS, 12/12

- [ ] **Step 4: Verify size**

Run: `wc -l frontend/src/features/scan-runs/ScanRunFindingsPanel.tsx`
Expected: under 200. Target ~70.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/scan-runs/ScanRunFindingsPanel.tsx frontend/src/features/scan-runs/ScanRunFindingsPanel.test.tsx
git commit -m "feat(frontend): ScanRunFindingsPanel component + tests"
```


---

### Task 7: `ScanRunEvidencePanel` component

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunEvidencePanel.tsx`
- Test: `frontend/src/features/scan-runs/ScanRunEvidencePanel.test.tsx`

**Columns:** Source, Target (first 8 chars, mono), URL (text, "—" if null), Method ("—" if null), Field ("—" if null), Matched value (mono, "—" if null), Created (date only). No badges — evidence has no severity/status fields.

- [ ] **Step 1: Write the failing test** — mirror `ScanRunFindingsPanel.test.tsx` exactly, swap names, columns, and assertions for evidence shape. Test count ~11 (one fewer than findings since there are no badges to assert).

- [ ] **Step 2: Implement** — `ScanRunEvidencePanel.tsx` (target ~70 lines)

Same skeleton as findings panel. Helper:

```ts
function dash(v: string | null): string {
  return v ?? "—";
}
```

Columns rendered:
```tsx
<td>{e.source}</td>
<td><code>{e.target.slice(0, 8)}</code></td>
<td>{dash(e.url)}</td>
<td>{dash(e.method)}</td>
<td>{dash(e.field)}</td>
<td><code>{dash(e.matched_value)}</code></td>
<td>{fmt(e.created_at)}</td>
```

Heading: `Evidence ({count})`. Empty state: `<p data-testid="evidence-empty">No evidence yet for this run.</p>`. Truncation footer text: `Showing first {results.length} of {count} evidence`. Truncation footer testid: `data-testid="evidence-truncation"`. Error callout: "Could not load evidence." Loading state testid: `data-testid="evidence-loading"`.

- [ ] **Step 3: Run tests**

Run: `npm test -C frontend -- ScanRunEvidencePanel.test.tsx --run`
Expected: PASS, 11/11

- [ ] **Step 4: Verify size**

Run: `wc -l frontend/src/features/scan-runs/ScanRunEvidencePanel.tsx`
Expected: under 200. Target ~70.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/scan-runs/ScanRunEvidencePanel.tsx frontend/src/features/scan-runs/ScanRunEvidencePanel.test.tsx
git commit -m "feat(frontend): ScanRunEvidencePanel component + tests"
```

---

### Phase 2 exit criteria

- [ ] `npm test -C frontend -- --run` green; 23+ new tests from this phase.
- [ ] `npm test -C frontend -- --coverage --run` shows 100 % on both new panel files.
- [ ] Both panel files under 200 lines.
- [ ] No regression in 6B tests (`ScanRunTargetsTable.test.tsx` still 12/12).
- [ ] `/simplify` round clean.
- [ ] Both panels NOT yet rendered anywhere — Phase 3 wires them.
