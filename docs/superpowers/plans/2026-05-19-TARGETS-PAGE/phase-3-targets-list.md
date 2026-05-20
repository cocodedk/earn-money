# Phase 3 — TargetsList page

The `/targets` list page. Mirrors `ProjectsList` shape but with a 6-column table and a project-name join via cached `useProjectsQuery`. Status badge rendered inline (no new primitive — uses Tailwind utilities directly).

---

### Task C: `TargetsList` page

**Files:**
- Create: `frontend/src/features/targets/TargetsList.tsx`
- Create: `frontend/src/features/targets/TargetsList.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/targets/TargetsList.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { TargetsList } from "./TargetsList";

const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 1,
  scan_run_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
};

const TARGET = {
  id: "t-1",
  project: "p-1",
  base_url: "https://dvwa.cocode.dk",
  host: "dvwa.cocode.dk",
  ip: null,
  status: "active" as const,
  created_at: "2026-05-19T08:00:00.000000Z",
  updated_at: "2026-05-19T08:00:00.000000Z",
};

function withProjects(rows: unknown[]) {
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({ count: rows.length, next: null, previous: null, results: rows }),
    ),
  );
}

function withTargets(rows: unknown[]) {
  server.use(
    msw.get("/api/targets/", () =>
      HttpResponse.json({ count: rows.length, next: null, previous: null, results: rows }),
    ),
  );
}

describe("TargetsList", () => {
  it("shows a skeleton while the list is loading", () => {
    withProjects([PROJECT]);
    withTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("shows the empty state with a Create target action", async () => {
    withProjects([PROJECT]);
    withTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText("No targets yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create target" })).toBeInTheDocument();
  });

  it("renders rows with the project name resolved from the cached projects query", async () => {
    withProjects([PROJECT]);
    withTargets([TARGET]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText("https://dvwa.cocode.dk")).toBeInTheDocument();
    expect(screen.getByText("dvwa.cocode.dk")).toBeInTheDocument();
    expect(screen.getByText("Local Lab")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("falls back to the short UUID when the target's project isn't in the cached list", async () => {
    withProjects([PROJECT]);
    withTargets([{ ...TARGET, project: "p-stale-aaaa-bbbb-cccc-dddd" }]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText("p-stale-")).toBeInTheDocument();
  });

  it("shows a Backend-unreachable callout with Retry on fetch error", async () => {
    withProjects([PROJECT]);
    server.use(msw.get("/api/targets/", () => HttpResponse.error()));
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
    let calls = 0;
    server.use(
      msw.get("/api/targets/", () => {
        calls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(0));
  });
});
```

- [ ] **Step 2: Run the test — it must fail**

```bash
cd frontend && npm run test -- src/features/targets/TargetsList
```

Expected: module-not-found error pointing at `./TargetsList`.

- [ ] **Step 3: Implement `TargetsList.tsx`**

Create `frontend/src/features/targets/TargetsList.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { useProjectsQuery } from "../projects/api";
import { useTargetsQuery } from "./api";
import type { Project, Target } from "../../types/api";

function buildColumns(
  projectName: (id: string) => string,
): TableColumn<Target>[] {
  return [
    { key: "base_url", header: "Base URL", cell: (t) => t.base_url },
    { key: "host", header: "Host", cell: (t) => t.host },
    { key: "ip", header: "IP", cell: (t) => t.ip ?? "—" },
    { key: "project", header: "Project", cell: (t) => projectName(t.project) },
    {
      key: "status",
      header: "Status",
      cell: (t) => <StatusBadge status={t.status} />,
    },
    {
      key: "created_at",
      header: "Created at",
      cell: (t) => t.created_at.slice(0, 10),
    },
  ];
}

function StatusBadge({ status }: { status: Target["status"] }) {
  const palette =
    status === "active"
      ? "bg-green-100 text-green-800"
      : "bg-gray-200 text-gray-700";
  return (
    <span
      data-testid={`status-${status}`}
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${palette}`}
    >
      {status}
    </span>
  );
}

function nameLookup(projects: Project[] | undefined) {
  const byId = new Map<string, string>();
  for (const p of projects ?? []) {
    byId.set(p.id, p.name);
  }
  return (id: string) => byId.get(id) ?? id.slice(0, 8);
}

export function TargetsList() {
  const targets = useTargetsQuery();
  const projects = useProjectsQuery();
  const navigate = useNavigate();
  const columns = buildColumns(nameLookup(projects.data?.results));
  return (
    <>
      <PageHeader
        title="Targets"
        action={
          <ButtonLink to={ROUTES.targetsNew} data-testid="page-header-create">
            Create target
          </ButtonLink>
        }
      />
      <div className="mt-4">
        {targets.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void targets.refetch() }}
          >
            Could not load targets.
          </Callout>
        ) : (
          <Table<Target>
            columns={columns}
            rows={targets.data?.results ?? []}
            rowKey={(t) => t.id}
            isLoading={targets.isLoading}
            emptyState={
              <EmptyState
                message="No targets yet."
                action={{
                  label: "Create target",
                  onClick: () => navigate(ROUTES.targetsNew),
                }}
              />
            }
          />
        )}
      </div>
    </>
  );
}
```

The file is ~95 lines including blanks — well under the 200-line cap. The status badge stays inline rather than being lifted to a primitive because it has exactly one consumer; YAGNI applies.

- [ ] **Step 4: Run the test — it must pass**

```bash
cd frontend && npm run test -- src/features/targets/TargetsList --coverage
```

Expected: all 5 tests pass; coverage 100% on `TargetsList.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/targets/TargetsList.tsx frontend/src/features/targets/TargetsList.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add TargetsList page with project-name join

Joins target.project (UUID) to project.name via cached useProjectsQuery —
no extra fetch on the common path. Falls back to the short UUID when
the target's project isn't in the list. Inline StatusBadge renders
active/retired without lifting to a new primitive (single consumer).
EmptyState wires "Create target" through useNavigate.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Run `/simplify` and iterate**

```bash
/simplify
```

Fix → commit → `/simplify` until clean.
