# Phase 2 — Table component + DetailPageGuard narrowing

Ship `ScanRunTargetsTable` plus the `DetailPageGuard` narrowing decided in §Decisions item 4 of the spec. Component-level tests cover happy / empty / loading / mixed-statuses / scoped-inline-error.

---

### Task A: Narrow `DetailPageGuard` to keep children mounted on background errors with stale data

**Files:**
- Modify: `frontend/src/components/DetailPageGuard/DetailPageGuard.tsx`
- Modify: `frontend/src/components/DetailPageGuard/DetailPageGuard.test.tsx`

- [ ] **Step 1: Write failing tests for the narrowed branches**

Append to `DetailPageGuard.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DetailPageGuard } from "./DetailPageGuard";

const OPTIONS = {
  notFoundTitle: "Not found",
  notFoundMessage: "Gone",
  backTo: "/",
  backLabel: "Back",
  errorTitle: "Error",
  errorBody: "Down",
};

function makeQuery<T>(over: Partial<{ data: T; error: unknown; isError: boolean }>) {
  return { data: undefined, error: null, isError: false, ...over } as never;
}

describe("DetailPageGuard background-error narrowing", () => {
  it("isError + has data → renders children, NO full-page takeover", () => {
    render(
      <MemoryRouter>
        <DetailPageGuard
          query={makeQuery({ data: { id: "x" }, error: new Error("net"), isError: true })}
          options={OPTIONS}
        >
          {(d) => <div data-testid="child">{d.id}</div>}
        </DetailPageGuard>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.queryByText("Down")).not.toBeInTheDocument();
  });

  it("404 + has data → renders children, NO not-found takeover", () => {
    const err = Object.assign(new Error("404"), { status: 404 });
    render(
      <MemoryRouter>
        <DetailPageGuard
          query={makeQuery({ data: { id: "x" }, error: err, isError: true })}
          options={OPTIONS}
        >
          {(d) => <div data-testid="child">{d.id}</div>}
        </DetailPageGuard>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.queryByText("Gone")).not.toBeInTheDocument();
  });
});
```

The existing "isError + no data → full-page" and "404 + no data → not-found" tests stay green to lock initial-load behavior.

- [ ] **Step 2: Run tests — must fail**

```bash
cd frontend && npm test -- src/components/DetailPageGuard/DetailPageGuard.test.tsx
```

Expected: FAIL — guard still triggers on isError/404 regardless of data.

- [ ] **Step 3: Narrow both takeover branches in `DetailPageGuard.tsx`**

```tsx
export function DetailPageGuard<T>({ query, options, children }: DetailPageGuardProps<T>): ReactElement {
  if (isHttpStatus(query.error, 404) && !query.data) {
    return (
      <>
        <PageHeader title={options.notFoundTitle} />
        <CalloutSlot>
          <Callout variant="info">
            {options.notFoundMessage}{" "}
            <Link to={options.backTo}>{options.backLabel}</Link>
          </Callout>
        </CalloutSlot>
      </>
    );
  }
  if (query.isError && !query.data) {
    return (
      <>
        <PageHeader title={options.errorTitle} />
        <CalloutSlot>
          <BackendUnreachableCallout>{options.errorBody}</BackendUnreachableCallout>
        </CalloutSlot>
      </>
    );
  }
  if (!query.data) {
    return <PageHeader title={options.loadingTitle ?? "Loading…"} />;
  }
  return children(query.data);
}
```

Only change: add `&& !query.data` to lines 29 and 42.

- [ ] **Step 4: Run tests — must pass**

```bash
cd frontend && npm test -- src/components/DetailPageGuard/DetailPageGuard.test.tsx
```

Expected: PASS for both new branches AND the existing 4 branches.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DetailPageGuard/DetailPageGuard.tsx frontend/src/components/DetailPageGuard/DetailPageGuard.test.tsx
git commit -m "feat(frontend): DetailPageGuard keeps children mounted on background errors with stale data"
```

Run `/simplify` to clean.

---

### Task B: `ScanRunTargetsTable` component

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunTargetsTable.tsx`

- [ ] **Step 1: Implement the component**

```tsx
import { useScanRunTargetRunsQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import { Callout } from "../../components/Callout";
import { Table } from "../../components/Table";
import type { ScanTargetRun } from "../../types/api";

export type ScanRunTargetsTableProps = {
  scanRunId: string;
  livePolling: boolean;
};

const fmt = (ts: string | null) => (ts ? ts.slice(0, 19) : "—");

export function ScanRunTargetsTable({ scanRunId, livePolling }: ScanRunTargetsTableProps) {
  const query = useScanRunTargetRunsQuery(scanRunId, { livePolling });

  if (query.isError) {
    return (
      <Callout variant="error">Could not load target rows. Refresh to retry.</Callout>
    );
  }
  if (!query.data) {
    return <div data-testid="targets-loading">Loading targets…</div>;
  }
  const { results, count, next } = query.data;
  if (count === 0) {
    return <div data-testid="targets-empty">No targets in this scan run.</div>;
  }
  return (
    <section>
      <Table>
        <thead>
          <tr>
            <th>Target</th>
            <th>Status</th>
            <th>Started at</th>
            <th>Finished at</th>
            <th>Findings</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r: ScanTargetRun) => (
            <tr key={r.id} data-testid={`target-run-row-${r.id}`}>
              <td>
                <div>{r.target_host}</div>
                <div>{r.target_base_url}</div>
              </td>
              <td><StatusBadge status={r.status} /></td>
              <td>{fmt(r.started_at)}</td>
              <td>{fmt(r.finished_at)}</td>
              <td>{r.findings_count}</td>
              <td>{r.evidence_count}</td>
            </tr>
          ))}
        </tbody>
      </Table>
      {next !== null && (
        <p data-testid="targets-truncation">
          Showing first {results.length} of {count} targets
        </p>
      )}
    </section>
  );
}
```

If the existing shared `Table` primitive lives elsewhere (`git grep -l "export.*Table" frontend/src/components`), adjust the import. Otherwise the cell rendering uses raw `<table>` — keep the file under 200 lines either way.

- [ ] **Step 2: Commit (test follows in Task C — file is meaningless alone)**

```bash
git add frontend/src/features/scan-runs/ScanRunTargetsTable.tsx
git commit -m "feat(frontend): ScanRunTargetsTable component"
```

---

### Task C: `ScanRunTargetsTable` tests

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunTargetsTable.test.tsx`

- [ ] **Step 1: Write the test file**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import { ScanRunTargetsTable } from "./ScanRunTargetsTable";

const handler = (rows: unknown[], over: { count?: number; next?: string | null } = {}) =>
  msw.get("/api/scan-runs/r-1/target-runs/", () =>
    HttpResponse.json({ count: over.count ?? rows.length, next: over.next ?? null, previous: null, results: rows }),
  );

describe("ScanRunTargetsTable", () => {
  it("renders rows with target_host, status badge, counts, timestamps", async () => {
    server.use(handler([
      makeScanTargetRun({
        id: "tr-1",
        target_host: "example.test",
        target_base_url: "https://example.test",
        status: "done",
        started_at: "2026-05-19T10:00:00Z",
        finished_at: "2026-05-19T10:01:23Z",
        findings_count: 2,
        evidence_count: 3,
      }),
    ]));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    const row = await screen.findByTestId("target-run-row-tr-1");
    expect(within(row).getByText("example.test")).toBeInTheDocument();
    expect(within(row).getByText("https://example.test")).toBeInTheDocument();
    expect(within(row).getByTestId("status-done")).toBeInTheDocument();
    expect(within(row).getByText("2026-05-19T10:00:00")).toBeInTheDocument();
    expect(within(row).getByText("2026-05-19T10:01:23")).toBeInTheDocument();
    expect(within(row).getByText("2")).toBeInTheDocument();
    expect(within(row).getByText("3")).toBeInTheDocument();
  });

  it("renders empty state when count is 0", async () => {
    server.use(handler([], { count: 0 }));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    expect(await screen.findByTestId("targets-empty")).toBeInTheDocument();
  });

  it("renders loading placeholder before first response", () => {
    server.use(handler([]));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    expect(screen.getByTestId("targets-loading")).toBeInTheDocument();
  });

  it.each([
    ["queued", null, null, "—", "—"],
    ["running", "2026-05-19T10:00:00Z", null, "2026-05-19T10:00:00", "—"],
    ["paused", "2026-05-19T10:00:00Z", null, "2026-05-19T10:00:00", "—"],
  ] as const)(
    "renders %s row with started_at=%s finished_at=%s → cells %s / %s",
    async (status, started_at, finished_at, startCell, finCell) => {
      server.use(handler([
        makeScanTargetRun({ id: `tr-${status}`, status, started_at, finished_at }),
      ]));
      renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
      const row = await screen.findByTestId(`target-run-row-tr-${status}`);
      const cells = within(row).getAllByRole("cell");
      expect(cells[2].textContent).toBe(startCell);
      expect(cells[3].textContent).toBe(finCell);
    },
  );

  it("renders failed-with-timestamp row (started_at + finished_at set)", async () => {
    server.use(handler([
      makeScanTargetRun({
        id: "tr-failed",
        status: "failed",
        started_at: "2026-05-19T10:00:00Z",
        finished_at: "2026-05-19T10:00:05Z",
      }),
    ]));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    const row = await screen.findByTestId("target-run-row-tr-failed");
    expect(within(row).getByTestId("status-failed")).toBeInTheDocument();
    expect(within(row).getByText("2026-05-19T10:00:05")).toBeInTheDocument();
  });

  it("renders stopped-from-queued row (null started_at, set finished_at)", async () => {
    server.use(handler([
      makeScanTargetRun({
        id: "tr-stopped-q",
        status: "stopped",
        started_at: null,
        finished_at: "2026-05-19T10:00:00Z",
      }),
    ]));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    const row = await screen.findByTestId("target-run-row-tr-stopped-q");
    const cells = within(row).getAllByRole("cell");
    expect(cells[2].textContent).toBe("—");
    expect(cells[3].textContent).toBe("2026-05-19T10:00:00");
  });

  it("renders truncation footer when next !== null", async () => {
    server.use(handler([makeScanTargetRun({ id: "tr-1" })], { count: 75, next: "?page=2" }));
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    expect(await screen.findByTestId("targets-truncation")).toHaveTextContent(
      "Showing first 1 of 75 targets",
    );
  });

  it("renders inline error callout on target-runs 500 (parent already loaded)", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => new HttpResponse(null, { status: 500 })),
    );
    renderWithProviders(<ScanRunTargetsTable scanRunId="r-1" livePolling={false} />);
    expect(await screen.findByText(/Could not load target rows/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests — must pass**

```bash
cd frontend && npm test -- src/features/scan-runs/ScanRunTargetsTable.test.tsx
```

Expected: PASS for all 8 cases.

- [ ] **Step 3: Coverage check + commit**

```bash
cd frontend && npm test -- --coverage
git add frontend/src/features/scan-runs/ScanRunTargetsTable.test.tsx
git commit -m "test(frontend): ScanRunTargetsTable component branches"
```

Run `/simplify` to clean.

---

### Phase 2 done

Component renders against the contract; DetailPageGuard narrowing locks the §Decisions item 4 behavior. Next: phase 3 — wire into `ScanRunDetail` + integration tests + E2E.
