# Phase 3 — Stubs feature

`/stubs` is read-only. Peer's contract (per their `2216e53` ping):
- `GET /api/stubs/` returns 278 rows, sorted by `phase.spec`, no pagination
- Row keys: `slug, phase, spec, title, status, fixture, category, phase_title, phase_slug, spec_slug, path`
- `GET /api/stubs/<slug>/` returns the same fields + `body` (raw markdown)
- 405 on POST/PUT/PATCH/DELETE

---

### Task H: Stubs API client

**Files:**
- Create: `frontend/src/features/stubs/api.ts`
- Create: `frontend/src/features/stubs/api.test.tsx`
- Modify: `frontend/src/types/api.ts` (add `Stub` + `StubDetail` types)

- [ ] **Step 1: Add types**

```ts
export type StubStatus = "pending" | "in_progress" | "done";

export type Stub = {
  slug: string;
  phase: number;
  spec: number;
  title: string;
  status: StubStatus;
  fixture: string | null;
  category: string;
  phase_title: string;
  phase_slug: string;
  spec_slug: string;
  path: string;
};

export type StubDetail = Stub & {
  body: string;
};
```

- [ ] **Step 2: Test**

```tsx
import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useStubsQuery, useStubDetailQuery } from "./api";

describe("useStubsQuery", () => {
  it("fetches the unpaginated stub list", async () => {
    server.use(
      msw.get("/api/stubs/", () =>
        HttpResponse.json([
          {
            slug: "1.1",
            phase: 1,
            spec: 1,
            title: "Framework detection",
            status: "done",
            fixture: "juiceshop",
            category: "information-gathering",
            phase_title: "Information gathering",
            phase_slug: "01-information-gathering",
            spec_slug: "01-framework-detection",
            path: "01-information-gathering/01-framework-detection.md",
          },
        ]),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.[0]?.slug).toBe("1.1"));
  });
});

describe("useStubDetailQuery", () => {
  it("fetches a stub by slug, including body", async () => {
    server.use(
      msw.get("/api/stubs/1.1/", () =>
        HttpResponse.json({
          slug: "1.1",
          phase: 1,
          spec: 1,
          title: "Framework detection",
          status: "done",
          fixture: "juiceshop",
          category: "information-gathering",
          phase_title: "Information gathering",
          phase_slug: "01-information-gathering",
          spec_slug: "01-framework-detection",
          path: "01-information-gathering/01-framework-detection.md",
          body: "# Framework detection\n\n…",
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubDetailQuery("1.1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.body).toContain("Framework detection"));
  });
});
```

- [ ] **Step 3: Implement**

```ts
import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Stub, StubDetail } from "../../types/api";

export const STUBS_KEY = ["stubs"] as const;

export function useStubsQuery() {
  return useQuery({
    queryKey: STUBS_KEY,
    queryFn: () => http<Stub[]>("/api/stubs/"),
  });
}

export function useStubDetailQuery(slug: string | null) {
  return useQuery({
    queryKey: [...STUBS_KEY, slug] as const,
    queryFn: () => http<StubDetail>(`/api/stubs/${encodeURIComponent(slug!)}/`),
    enabled: Boolean(slug),
  });
}
```

- [ ] **Step 4: Commit + /simplify**

```bash
npm run test -- src/features/stubs/api
git add frontend/src/features/stubs/api.{ts,test.tsx} frontend/src/types/api.ts
git commit -m "feat(frontend): add Stubs API client (read-only)"
```

---

### Task I: `StubsList` page

**Files:**
- Create: `frontend/src/features/stubs/StubsList.tsx`
- Create: `frontend/src/features/stubs/StubsList.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { StubsList } from "./StubsList";

const fixtures = [
  {
    slug: "1.1",
    phase: 1,
    spec: 1,
    title: "Framework detection",
    status: "done",
    fixture: "juiceshop",
    category: "information-gathering",
    phase_title: "Information gathering",
    phase_slug: "01-information-gathering",
    spec_slug: "01-framework-detection",
    path: "x",
  },
  {
    slug: "1.2",
    phase: 1,
    spec: 2,
    title: "Server headers",
    status: "in_progress",
    fixture: null,
    category: "information-gathering",
    phase_title: "Information gathering",
    phase_slug: "01-information-gathering",
    spec_slug: "02-server-headers",
    path: "x",
  },
];

describe("StubsList", () => {
  it("renders rows sorted by phase.spec with phase/spec/title columns", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.json(fixtures)));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText("Framework detection")).toBeInTheDocument();
    expect(screen.getByText("Server headers")).toBeInTheDocument();
    expect(screen.getAllByTestId("status-badge")[0]).toHaveAttribute(
      "data-status",
      "done",
    );
  });

  it("each row links to /stubs/<slug>", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.json(fixtures)));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    const link = await screen.findByRole("link", { name: "Framework detection" });
    expect(link).toHaveAttribute("href", "/stubs/1.1");
  });

  it("shows the empty state when no stubs are returned", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.json([])));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText(/no stubs/i)).toBeInTheDocument();
  });

  it("renders a callout with retry on fetch error", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.error()));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `StubsList.tsx`**

```tsx
import { Link } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { StatusBadge } from "../../components/StatusBadge";
import { useStubsQuery } from "./api";
import type { Stub, StatusBadgeStatus } from "../../types/api";

function stubStatusToBadge(status: Stub["status"]): StatusBadgeStatus {
  // Stub workflow statuses (pending / in_progress / done) don't fully overlap with
  // ScanRun statuses; map to the closest visual.
  if (status === "done") return "done";
  if (status === "in_progress") return "running";
  return "queued";
}

const columns: TableColumn<Stub>[] = [
  { key: "slug", header: "Slug", cell: (r) => r.slug },
  { key: "phase", header: "Phase", cell: (r) => r.phase_title },
  {
    key: "title",
    header: "Title",
    cell: (r) => (
      <Link to={`/stubs/${r.slug}`} className="text-blue-700 hover:underline">
        {r.title}
      </Link>
    ),
  },
  { key: "category", header: "Category", cell: (r) => r.category },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge status={stubStatusToBadge(r.status)} />,
  },
  { key: "fixture", header: "Fixture", cell: (r) => r.fixture ?? "—" },
];

export function StubsList() {
  const query = useStubsQuery();
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
          <Table<Stub>
            columns={columns}
            rows={query.data ?? []}
            rowKey={(r) => r.slug}
            isLoading={query.isLoading}
            emptyState={<EmptyState message="No stubs available." />}
          />
        )}
      </div>
    </>
  );
}
```

Note: `Stub["status"]` (`pending | in_progress | done`) doesn't overlap with `StatusBadge`'s `ScanRunStatus | TargetStatus` union. The mapping is local to this file.

- [ ] **Step 3: Run + commit + /simplify**

```bash
npm run test -- src/features/stubs/StubsList
git add frontend/src/features/stubs/StubsList.{tsx,test.tsx}
git commit -m "feat(frontend): add StubsList page"
```

---

### Task J: `StubDetail` page

**Files:**
- Create: `frontend/src/features/stubs/StubDetail.tsx`
- Create: `frontend/src/features/stubs/StubDetail.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { Route, Routes } from "react-router-dom";
import { StubDetail } from "./StubDetail";

function mountAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/stubs/:slug" element={<StubDetail />} />
    </Routes>,
    { route },
  );
}

describe("StubDetail", () => {
  it("renders the stub detail fields and the body", async () => {
    server.use(
      msw.get("/api/stubs/1.1/", () =>
        HttpResponse.json({
          slug: "1.1",
          phase: 1,
          spec: 1,
          title: "Framework detection",
          status: "done",
          fixture: "juiceshop",
          category: "information-gathering",
          phase_title: "Information gathering",
          phase_slug: "01-information-gathering",
          spec_slug: "01-framework-detection",
          path: "x",
          body: "# Framework detection\n\nDetect the running framework.",
        }),
      ),
    );
    mountAt("/stubs/1.1");
    expect(await screen.findByText("Framework detection")).toBeInTheDocument();
    expect(screen.getByText("information-gathering")).toBeInTheDocument();
    expect(screen.getByText(/Detect the running framework/)).toBeInTheDocument();
  });

  it("renders a callout when the stub is not found", async () => {
    server.use(
      msw.get("/api/stubs/9.9/", () =>
        HttpResponse.json({ detail: "Not found." }, { status: 404 }),
      ),
    );
    mountAt("/stubs/9.9");
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `StubDetail.tsx`**

```tsx
import { useParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import { useStubDetailQuery } from "./api";

export function StubDetail() {
  const { slug = null } = useParams();
  const query = useStubDetailQuery(slug);

  if (query.isError) {
    return (
      <>
        <PageHeader title={`Stub ${slug ?? ""}`} />
        <div className="mt-4">
          <Callout variant="error" title="Not found">
            This stub could not be loaded.
          </Callout>
        </div>
      </>
    );
  }

  const stub = query.data;
  return (
    <>
      <PageHeader title={stub?.title ?? `Stub ${slug ?? ""}`} />
      {stub && (
        <div className="mt-4 grid grid-cols-[160px_1fr] gap-y-2 max-w-3xl text-sm">
          <div className="text-gray-600">Slug</div>
          <div className="font-mono">{stub.slug}</div>
          <div className="text-gray-600">Phase</div>
          <div>{stub.phase_title}</div>
          <div className="text-gray-600">Category</div>
          <div>{stub.category}</div>
          <div className="text-gray-600">Fixture</div>
          <div>{stub.fixture ?? "—"}</div>
          <div className="text-gray-600">Path</div>
          <div className="font-mono">{stub.path}</div>
          <div className="col-span-2 mt-4">
            <pre className="whitespace-pre-wrap font-mono text-xs bg-gray-50 border border-gray-200 rounded p-3 max-h-96 overflow-auto">
              {stub.body}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}
```

The spec body is rendered in a `<pre>` for now — markdown rendering is deferred (don't add a markdown library until a real UX need emerges).

- [ ] **Step 3: Run + commit + /simplify**

```bash
npm run test -- src/features/stubs/StubDetail
git add frontend/src/features/stubs/StubDetail.{tsx,test.tsx}
git commit -m "feat(frontend): add StubDetail page"
```
