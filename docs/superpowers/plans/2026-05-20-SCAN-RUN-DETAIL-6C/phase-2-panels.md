# Phase 2 — Panel components

**Goal:** Ship `ScanRunFindingsPanel` and `ScanRunEvidencePanel` — both read-only tables, scan-run-scoped, taking `(scanRunId, livePolling)` and rendering loading / empty / error / table / truncation states. Not yet wired into `ScanRunDetail` (that's Phase 3).

**Reference patterns:** `frontend/src/features/scan-runs/ScanRunTargetsTable.tsx` (64 lines) is the canonical template. Both new panels mirror its structure exactly: raw `<table>`, inline `fmt` helper, `<Callout>` for errors, truncation footer with testid, per-row `data-testid` for transition tests.

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

Test cases (~12):
1. Renders heading "Findings (N)" where N is `data.count`
2. Renders the seven columns: Title, Target, Category, Severity, Confidence, Status, Created
3. Renders one row per finding in `data.results`
4. Each row has `data-testid="finding-row-{id}"`
5. Renders skeleton/`...` while `isLoading`
6. Renders `<Callout>` with "Could not load findings" when query errors
7. Renders empty state ("No findings yet for this run.") when `data.results.length === 0`
8. Truncates timestamp: `created_at: "2026-05-20T08:00:00Z"` → `"2026-05-20"`
9. Renders truncation footer with `data-testid="findings-truncation"` when `data.next !== null`
10. Does NOT render truncation footer when `data.next === null`
11. Truncation footer text reads `Showing first {results.length} of {count} findings` (mirrors shipped 6B `ScanRunTargetsTable.tsx` text exactly — no hardcoded `50`)
12. Severity, confidence, status render as plain text in their cells (assert `getByText("low")` resolves inside `finding-row-{id}`)

```tsx
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { ScanRunFindingsPanel } from "./ScanRunFindingsPanel";
import { makeFinding } from "./__fixtures__/finding";

function wrap(children: ReactNode) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  );
}

const SCAN_RUN_ID = "s1111111-1111-1111-1111-111111111111";

describe("ScanRunFindingsPanel", () => {
  it("renders heading with count", async () => {
    server.use(
      http.get("/api/findings/", () =>
        HttpResponse.json({
          count: 3, next: null, previous: null,
          results: [
            makeFinding({ id: "f1", title: "A" }),
            makeFinding({ id: "f2", title: "B" }),
            makeFinding({ id: "f3", title: "C" }),
          ],
        }),
      ),
    );
    wrap(<ScanRunFindingsPanel scanRunId={SCAN_RUN_ID} livePolling={false} />);
    expect(await screen.findByText(/Findings \(3\)/)).toBeInTheDocument();
  });

  // remaining 11 tests follow the same shape — see ScanRunTargetsTable.test.tsx
  // for the verbatim style: each test sets up MSW, renders the panel, asserts
  // one observable behaviour.
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
