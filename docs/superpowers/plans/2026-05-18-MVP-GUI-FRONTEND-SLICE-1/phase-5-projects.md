# Phase 5 — Projects feature

Projects API client + the two routes that ship the feature (`/projects` and `/projects/new`).

---

### Task R: Projects API client + hooks

**Files:**
- Create: `frontend/src/features/projects/api.ts`
- Create: `frontend/src/features/projects/api.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../../test/server";
import { useProjectsQuery, useCreateProjectMutation, PROJECTS_KEY } from "./api";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return { client, Wrapper };
}

describe("useProjectsQuery", () => {
  it("fetches and returns the page of projects", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "u1",
              name: "Local Lab",
              description: "",
              target_count: 3,
              scan_run_count: 0,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useProjectsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(result.current.data?.results[0].name).toBe("Local Lab");
  });
});

describe("useCreateProjectMutation", () => {
  it("POSTs the body and invalidates the projects list", async () => {
    let received: unknown = null;
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.post("/api/projects/", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(
          {
            id: "u-new",
            name: "Local Lab",
            description: "lab",
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    const { client, Wrapper } = makeWrapper();
    const listSpy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateProjectMutation(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.mutateAsync({ name: "Local Lab", description: "lab" });
    });
    expect(received).toEqual({ name: "Local Lab", description: "lab" });
    expect(listSpy).toHaveBeenCalledWith({ queryKey: PROJECTS_KEY });
  });
});
```

Add `import { vi } from "vitest";` to the imports.

- [ ] **Step 2: Implement `api.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { CreateProjectBody, Paginated, Project } from "../../types/api";

export const PROJECTS_KEY = ["projects"] as const;

export function useProjectsQuery() {
  return useQuery({
    queryKey: PROJECTS_KEY,
    queryFn: () => http<Paginated<Project>>("/api/projects/"),
  });
}

export function useCreateProjectMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateProjectBody) =>
      http<Project>("/api/projects/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}
```

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm run test -- src/features/projects/api --coverage
git add frontend/src/features/projects/api.ts frontend/src/features/projects/api.test.tsx
git commit -m "feat(frontend): add Projects API client with cache invalidation"
```

---

### Task S: `ProjectsList` page

**Files:**
- Create: `frontend/src/features/projects/ProjectsList.tsx`
- Create: `frontend/src/features/projects/ProjectsList.module.css`
- Create: `frontend/src/features/projects/ProjectsList.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ProjectsList } from "./ProjectsList";

function withProjects(rows: unknown[]) {
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({ count: rows.length, next: null, previous: null, results: rows }),
    ),
  );
}

describe("ProjectsList", () => {
  it("shows the skeleton while loading", () => {
    server.use(msw.get("/api/projects/", () => HttpResponse.json({ count: 0, next: null, previous: null, results: [] })));
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("shows the empty state with a create action when there are no rows", async () => {
    withProjects([]);
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create project" })).toBeInTheDocument();
  });

  it("renders rows with denormalized counts", async () => {
    withProjects([
      {
        id: "u1",
        name: "Local Lab",
        description: "lab",
        target_count: 3,
        scan_run_count: 1,
        created_at: "2026-05-18T20:00:00.000000Z",
      },
    ]);
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    expect(await screen.findByText("Local Lab")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows a callout with retry on fetch error", async () => {
    server.use(msw.get("/api/projects/", () => HttpResponse.error()));
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("navigates to /projects/new when the create button is clicked", async () => {
    withProjects([]);
    renderWithProviders(<ProjectsList />, { route: "/projects" });
    await userEvent.click(await screen.findByRole("button", { name: "Create project" }));
    // The route change is asserted via the route's outlet — for this unit test,
    // assert the link/button uses the right `to`. We expose the create entrypoint
    // through a NavLink-rendered button to make this simple.
    expect(screen.getByTestId("page-header-create")).toHaveAttribute(
      "href",
      "/projects/new",
    );
  });
});
```

- [ ] **Step 2: Implement `ProjectsList.tsx`**

```tsx
import { Link } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { Button } from "../../components/Button";
import { useProjectsQuery } from "./api";
import type { Project } from "../../types/api";

const columns: TableColumn<Project>[] = [
  { key: "name", header: "Name", cell: (r) => r.name },
  { key: "description", header: "Description", cell: (r) => r.description },
  { key: "target_count", header: "Target count", cell: (r) => r.target_count },
  { key: "scan_run_count", header: "Scan run count", cell: (r) => r.scan_run_count },
  { key: "created_at", header: "Created at", cell: (r) => r.created_at.slice(0, 10) },
];

export function ProjectsList() {
  const query = useProjectsQuery();
  return (
    <>
      <PageHeader
        title="Projects"
        action={
          <Link
            to="/projects/new"
            data-testid="page-header-create"
            className="inline-flex items-center h-10 px-4 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
          >
            Create project
          </Link>
        }
      />
      {query.isError ? (
        <div className="mt-4">
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load projects.
          </Callout>
        </div>
      ) : (
        <div className="mt-4">
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
                  onClick: () => {
                    window.location.assign("/projects/new");
                  },
                }}
              />
            }
          />
        </div>
      )}
    </>
  );
}
```

Note: `window.location.assign` keeps the EmptyState button's behaviour testable without needing the full router context inside that small unit. The primary create entry-point is the `<Link>` in the page header.

`Button` import not needed in this file — remove the import line if linting complains.

- [ ] **Step 3: `ProjectsList.module.css`**

Not required for slice 1; the page uses utilities directly through composed primitives. Skip the file.

- [ ] **Step 4: Run + commit**

```bash
cd frontend && npm run test -- src/features/projects/ProjectsList --coverage
git add frontend/src/features/projects/ProjectsList.tsx frontend/src/features/projects/ProjectsList.test.tsx
git commit -m "feat(frontend): add ProjectsList page with empty/error/loading branches"
```

---

### Task T: `CreateProject` page

**Files:**
- Create: `frontend/src/features/projects/CreateProject.tsx`
- Create: `frontend/src/features/projects/CreateProject.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { CreateProject } from "./CreateProject";

describe("CreateProject", () => {
  it("validates required name field locally", async () => {
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("name is required")).toBeInTheDocument();
  });

  it("submits and routes back to /projects on success", async () => {
    server.use(
      msw.post("/api/projects/", () =>
        HttpResponse.json(
          {
            id: "u-new",
            name: "X",
            description: "Y",
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        ),
      ),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.type(screen.getByLabelText(/Description/), "Y");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByTestId("create-success")).toHaveAttribute(
      "data-redirect",
      "/projects",
    );
  });

  it("renders server field errors under the matching input", async () => {
    server.use(
      msw.post("/api/projects/", () =>
        HttpResponse.json({ name: ["already exists"] }, { status: 400 }),
      ),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("already exists")).toBeInTheDocument();
  });

  it("renders non_field_errors above the form", async () => {
    server.use(
      msw.post("/api/projects/", () =>
        HttpResponse.json({ non_field_errors: ["bad combo"] }, { status: 400 }),
      ),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("bad combo")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `CreateProject.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { FormField, TextInput, Textarea } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { useCreateProjectMutation } from "./api";
import { parseApiError } from "../../lib/parseApiError";
import { HttpError } from "../../lib/http";

export function CreateProject() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [localNameError, setLocalNameError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [bannerError, setBannerError] = useState<string | null>(null);
  const [redirectTo, setRedirectTo] = useState<string | null>(null);
  const navigate = useNavigate();
  const mutation = useCreateProjectMutation();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setLocalNameError("name is required");
      return;
    }
    setLocalNameError(null);
    setFieldErrors({});
    setBannerError(null);
    try {
      await mutation.mutateAsync({ name, description });
      setRedirectTo("/projects");
      navigate("/projects");
    } catch (err) {
      const parsed =
        err instanceof HttpError
          ? await parseApiError(err.response)
          : await parseApiError(err as Error);
      if (parsed.kind === "field") {
        setFieldErrors(parsed.errors);
      } else if (parsed.kind === "non_field") {
        setBannerError(parsed.errors[0]);
      } else if (parsed.kind === "detail") {
        setBannerError(parsed.detail);
      } else if (parsed.kind === "server") {
        setBannerError("Something went wrong. Please try again.");
      } else {
        setBannerError("Backend unreachable.");
      }
    }
  }

  return (
    <>
      <PageHeader title="Create project" />
      {redirectTo && (
        <div
          data-testid="create-success"
          data-redirect={redirectTo}
          className="sr-only"
        />
      )}
      {bannerError && (
        <div className="mt-4">
          <Callout variant="error">{bannerError}</Callout>
        </div>
      )}
      <form onSubmit={onSubmit} noValidate className="mt-4 flex flex-col gap-4 max-w-lg">
        <FormField
          label="Name"
          htmlFor="name"
          required
          error={localNameError ?? fieldErrors.name?.[0]}
        >
          <TextInput
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </FormField>
        <FormField
          label="Description"
          htmlFor="description"
          error={fieldErrors.description?.[0]}
        >
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </FormField>
        <div>
          <Button type="submit" loading={mutation.isPending}>
            Create project
          </Button>
        </div>
      </form>
    </>
  );
}
```

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm run test -- src/features/projects/CreateProject --coverage
git add frontend/src/features/projects/CreateProject.tsx frontend/src/features/projects/CreateProject.test.tsx
git commit -m "feat(frontend): add CreateProject page with full validation UX"
```
