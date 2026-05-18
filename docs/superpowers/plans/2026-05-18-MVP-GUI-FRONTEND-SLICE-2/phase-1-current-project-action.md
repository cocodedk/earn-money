# Phase 1 — Set-as-current row action on `/projects`

Closes the slice-1.1 UX gap: the `CurrentProjectChip` switch link routes to `/projects` but the list doesn't expose any "set as current" action. After this phase, each row has a button that calls `setId(project.id)` from `useCurrentProject`, the top-bar chip updates, and clicking switch on a different chip returns to the list.

---

### Task D: Add "Set as current" action column to `ProjectsList`

**Files:**
- Modify: `frontend/src/features/projects/ProjectsList.tsx`
- Modify: `frontend/src/features/projects/ProjectsList.test.tsx`

- [ ] **Step 1: Write failing tests for the action**

Append to `ProjectsList.test.tsx`:

```tsx
it("shows a 'Set as current' button on each row, wiring it to useCurrentProject", async () => {
  withProjects([
    {
      id: "u-1",
      name: "Lab A",
      description: "",
      target_count: 0,
      scan_run_count: 0,
      created_at: "2026-05-18T20:00:00.000000Z",
    },
    {
      id: "u-2",
      name: "Lab B",
      description: "",
      target_count: 0,
      scan_run_count: 0,
      created_at: "2026-05-18T20:00:00.000000Z",
    },
  ]);
  renderWithProviders(<ProjectsList />, { route: "/projects" });
  await screen.findByText("Lab A");
  const buttons = screen.getAllByRole("button", { name: /set as current/i });
  expect(buttons).toHaveLength(2);
  await userEvent.click(buttons[1]);
  expect(window.localStorage.getItem("em.frontend.currentProjectId")).toBe("u-2");
});

it("marks the current row when localStorage matches", async () => {
  window.localStorage.setItem("em.frontend.currentProjectId", "u-1");
  withProjects([
    {
      id: "u-1",
      name: "Lab A",
      description: "",
      target_count: 0,
      scan_run_count: 0,
      created_at: "2026-05-18T20:00:00.000000Z",
    },
  ]);
  renderWithProviders(<ProjectsList />, { route: "/projects" });
  expect(await screen.findByText("Current")).toBeInTheDocument();
});
```

Also import `userEvent` from `@testing-library/user-event` at the top if not already present (slice 1 already imports it).

- [ ] **Step 2: Run, see fail**

```bash
npm run test -- src/features/projects/ProjectsList
```

Expected: FAIL — no "Set as current" buttons rendered yet.

- [ ] **Step 3: Modify `ProjectsList.tsx`**

Replace the file with:

```tsx
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { Button } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { useProjectsQuery } from "./api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import type { Project } from "../../types/api";

export function ProjectsList() {
  const query = useProjectsQuery();
  const navigate = useNavigate();
  const { id: currentId, setId } = useCurrentProject();

  const columns: TableColumn<Project>[] = [
    { key: "name", header: "Name", cell: (r) => r.name },
    { key: "description", header: "Description", cell: (r) => r.description },
    { key: "target_count", header: "Target count", cell: (r) => r.target_count },
    { key: "scan_run_count", header: "Scan run count", cell: (r) => r.scan_run_count },
    { key: "created_at", header: "Created at", cell: (r) => r.created_at.slice(0, 10) },
    {
      key: "actions",
      header: "Actions",
      cell: (r) =>
        r.id === currentId ? (
          <span className="text-sm font-medium text-blue-700">Current</span>
        ) : (
          <Button variant="secondary" onClick={() => setId(r.id)}>
            Set as current
          </Button>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Projects"
        action={
          <ButtonLink to={ROUTES.projectsNew} data-testid="page-header-create">
            Create project
          </ButtonLink>
        }
      />
      <div className="mt-4">
        {query.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load projects.
          </Callout>
        ) : (
          <Table<Project>
            columns={columns}
            rows={query.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={query.isLoading}
            emptyState={
              <EmptyState
                message="No projects yet."
                action={{
                  label: "Create project",
                  onClick: () => navigate(ROUTES.projectsNew),
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

Note: `columns` moves inside the component because the `actions` cell closures over `currentId` and `setId`. The closure is fine for slice-2 scale; memoize only if profiling shows it matters.

- [ ] **Step 4: Run, verify the two new tests pass + existing 6 still green**

```bash
npm run test -- src/features/projects/ProjectsList --coverage
```

Expected: 8 passed; 100% coverage on `ProjectsList.tsx`.

- [ ] **Step 5: Commit + /simplify**

```bash
git add frontend/src/features/projects/ProjectsList.{tsx,test.tsx}
git commit -m "feat(frontend): add 'Set as current' row action on ProjectsList (slice-1.1 follow-up)"
```
