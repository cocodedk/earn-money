# Phase 3 — StubsList page

List page over `/api/stubs/`. Status badge palette is tuned per peer micro-nit (`blocked = amber`). Slug cell doubles as a `<Link>` so the row click target is bigger.

---

### Task C: `StubsList` page

**Files:**
- Create: `frontend/src/features/stubs/StubsList.tsx`
- Create: `frontend/src/features/stubs/StubsList.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/stubs/StubsList.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { LocationProbe, withBareArray } from "../../test/helpers";
import { StubsList } from "./StubsList";

function stub(overrides: Record<string, unknown> = {}) {
  return {
    slug: "1.1",
    phase: 1,
    spec: 1,
    phase_slug: "01-information-gathering",
    spec_slug: "framework-detection",
    title: "Framework detection",
    phase_title: "Information gathering",
    category: "Content discovery",
    status: "done",
    fixture: "juice-shop",
    path: "01-information-gathering/01-framework-detection.md",
    ...overrides,
  };
}

describe("StubsList", () => {
  it("shows a skeleton while loading", () => {
    withBareArray("/api/stubs/", []);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("shows an empty state when there are no stubs", async () => {
    withBareArray("/api/stubs/", []);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText("No stubs found.")).toBeInTheDocument();
  });

  it("renders rows with status badges and slug-as-link", async () => {
    withBareArray("/api/stubs/", [stub()]);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText("Framework detection")).toBeInTheDocument();
    expect(screen.getByText("framework-detection")).toBeInTheDocument();
    expect(screen.getByTestId("status-done")).toBeInTheDocument();
    const slugLink = screen.getByRole("link", { name: "1.1" });
    expect(slugLink).toHaveAttribute("href", "/stubs/1.1");
  });

  it("renders all four status badges with the right palette", async () => {
    withBareArray("/api/stubs/", [
      stub({ slug: "1.1", status: "done" }),
      stub({ slug: "1.2", status: "in-progress" }),
      stub({ slug: "1.3", status: "blocked" }),
      stub({ slug: "1.4", status: "pending" }),
    ]);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    await screen.findByTestId("status-done");
    expect(screen.getByTestId("status-done").className).toMatch(/bg-green/);
    expect(screen.getByTestId("status-in-progress").className).toMatch(/bg-blue/);
    expect(screen.getByTestId("status-blocked").className).toMatch(/bg-amber/);
    expect(screen.getByTestId("status-pending").className).toMatch(/bg-gray/);
  });

  it("renders an empty-string spec_slug as the em-dash placeholder", async () => {
    withBareArray("/api/stubs/", [stub({ spec_slug: "" })]);
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText("—")).toBeInTheDocument();
  });

  it("shows a Backend-unreachable callout with Retry on fetch error", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.error()));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
    let calls = 0;
    server.use(
      msw.get("/api/stubs/", () => {
        calls += 1;
        return HttpResponse.json([]);
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(0));
  });

  it("navigates to the detail page when a slug link is clicked", async () => {
    withBareArray("/api/stubs/", [stub()]);
    renderWithProviders(
      <>
        <StubsList />
        <LocationProbe />
      </>,
      { route: "/stubs" },
    );
    await userEvent.click(await screen.findByRole("link", { name: "1.1" }));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/stubs/1.1"),
    );
  });
});
```

- [ ] **Step 2: Run the test — it must fail**

```bash
cd frontend && npm test -- src/features/stubs/StubsList
```

Expected: module-not-found.

- [ ] **Step 3: Implement `StubsList.tsx`**

```tsx
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ROUTES, stubDetailPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { useStubsQuery } from "./api";
import type { StubSummary } from "../../types/api";

const STATUS_PALETTE: Record<StubSummary["status"], string> = {
  done: "bg-green-100 text-green-800",
  "in-progress": "bg-blue-100 text-blue-800",
  blocked: "bg-amber-100 text-amber-800",
  pending: "bg-gray-200 text-gray-700",
};

function StatusBadge({ status }: { status: StubSummary["status"] }) {
  return (
    <span
      data-testid={`status-${status}`}
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_PALETTE[status]}`}
    >
      {status}
    </span>
  );
}

function buildColumns(): TableColumn<StubSummary>[] {
  return [
    { key: "phase", header: "Phase", cell: (s) => s.phase },
    { key: "spec", header: "Spec", cell: (s) => s.spec },
    {
      key: "slug",
      header: "Slug",
      cell: (s) => (
        <Link to={stubDetailPath(s.slug)}>{s.spec_slug || "—"}</Link>
      ),
    },
    { key: "title", header: "Title", cell: (s) => s.title },
    { key: "status", header: "Status", cell: (s) => <StatusBadge status={s.status} /> },
    { key: "fixture", header: "Fixture", cell: (s) => s.fixture },
    {
      key: "actions",
      header: "Actions",
      cell: (s) => (
        <ButtonLink to={stubDetailPath(s.slug)} variant="secondary">
          View
        </ButtonLink>
      ),
    },
  ];
}
```

Wait — the test asserts `screen.getByRole("link", { name: "1.1" })` (the composite slug) but the cell renders `spec_slug || "—"` (the kebab-case label). That's the wrong link text. Fix the cell:

```tsx
{
  key: "slug",
  header: "Slug",
  cell: (s) => <Link to={stubDetailPath(s.slug)}>{s.slug}</Link>,
},
{
  key: "spec_slug",
  header: "Spec slug",
  cell: (s) => s.spec_slug || "—",
},
```

That gives 8 columns. Updated test assertions: `screen.getByRole("link", { name: "1.1" })` finds the composite-slug link; `screen.getByText("framework-detection")` finds the spec_slug cell. Re-check the test file — the existing assertions already cover both.

Updated `buildColumns`:

```ts
function buildColumns(): TableColumn<StubSummary>[] {
  return [
    { key: "phase", header: "Phase", cell: (s) => s.phase },
    { key: "spec", header: "Spec", cell: (s) => s.spec },
    {
      key: "slug",
      header: "Slug",
      cell: (s) => <Link to={stubDetailPath(s.slug)}>{s.slug}</Link>,
    },
    { key: "spec_slug", header: "Spec slug", cell: (s) => s.spec_slug || "—" },
    { key: "title", header: "Title", cell: (s) => s.title },
    {
      key: "status",
      header: "Status",
      cell: (s) => <StatusBadge status={s.status} />,
    },
    { key: "fixture", header: "Fixture", cell: (s) => s.fixture },
    {
      key: "actions",
      header: "Actions",
      cell: (s) => (
        <ButtonLink to={stubDetailPath(s.slug)} variant="secondary">
          View
        </ButtonLink>
      ),
    },
  ];
}
```

Then the page body:

```tsx
export function StubsList() {
  const query = useStubsQuery();
  const columns = useMemo(buildColumns, []);
  return (
    <>
      <PageHeader title="Stubs" />
      <div className="mt-4">
        {query.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load stubs.
          </Callout>
        ) : (
          <Table<StubSummary>
            columns={columns}
            rows={query.data ?? []}
            rowKey={(s) => s.slug}
            isLoading={query.isLoading}
            emptyState={<EmptyState message="No stubs found." />}
          />
        )}
      </div>
    </>
  );
}
```

Notes:
- The `slug` column header reads "Slug" (composite id) and `spec_slug` reads "Spec slug" (kebab label) — clearer than the spec's "Slug" alone but consistent with the actual data. Adjust the table column headers in the spec if needed.
- `useMemo(buildColumns, [])` is cheap; consistent with Targets' memoisation.

- [ ] **Step 4: Run + verify all branches**

```bash
cd frontend && npm test -- src/features/stubs/StubsList --coverage
```

Expected: 7 tests pass; 100% coverage on `StubsList.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stubs/StubsList.tsx frontend/src/features/stubs/StubsList.test.tsx
git commit -m "feat(frontend): add StubsList page with status palette + slug-as-link"
```
