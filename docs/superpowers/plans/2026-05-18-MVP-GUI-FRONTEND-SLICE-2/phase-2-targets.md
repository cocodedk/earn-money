# Phase 2 — Targets feature

`/targets` list + Add target form, matching `03-targets.md` and peer's `/api/targets/` contract (filter list with `?project=<uuid>`; uniqueness on `(project, base_url)` returns 400 with `non_field_errors`).

---

### Task E: Targets API client

**Files:**
- Create: `frontend/src/features/targets/api.ts`
- Create: `frontend/src/features/targets/api.test.tsx`
- Modify: `frontend/src/types/api.ts` (add `Target` + `CreateTargetBody` types)

- [ ] **Step 1: Add types to `src/types/api.ts`**

```ts
export type Target = {
  id: Uuid;
  project: Uuid;
  base_url: string;
  host: string | null;
  ip: string | null;
  status: TargetStatus;
  created_at: Iso8601;
};

export type CreateTargetBody = {
  project: Uuid;
  base_url: string;
  host?: string | null;
  ip?: string | null;
  status?: TargetStatus;
};
```

- [ ] **Step 2: Test `api.ts`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useTargetsQuery, useCreateTargetMutation, TARGETS_KEY } from "./api";

describe("useTargetsQuery", () => {
  it("fetches targets filtered by project", async () => {
    let requestedUrl: URL | null = null;
    server.use(
      msw.get("/api/targets/", ({ request }) => {
        requestedUrl = new URL(request.url);
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "t1",
              project: "p1",
              base_url: "https://dvwa.cocode.dk",
              host: null,
              ip: null,
              status: "active",
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetsQuery("p1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(requestedUrl?.searchParams.get("project")).toBe("p1");
  });

  it("omits the project filter when projectId is null", async () => {
    let requestedUrl: URL | null = null;
    server.use(
      msw.get("/api/targets/", ({ request }) => {
        requestedUrl = new URL(request.url);
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useTargetsQuery(null), { wrapper: Wrapper });
    await waitFor(() => expect(requestedUrl).not.toBeNull());
    expect(requestedUrl?.searchParams.has("project")).toBe(false);
  });
});

describe("useCreateTargetMutation", () => {
  it("POSTs the body and invalidates targets + projects (denormalized counts)", async () => {
    let received: unknown = null;
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(
          {
            id: "t-new",
            project: "p1",
            base_url: "https://x",
            host: null,
            ip: null,
            status: "active",
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateTargetMutation(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        project: "p1",
        base_url: "https://x",
      });
    });
    expect(received).toMatchObject({ project: "p1", base_url: "https://x" });
    expect(spy).toHaveBeenCalledWith({ queryKey: TARGETS_KEY });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});
```

- [ ] **Step 3: Implement `api.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import { PROJECTS_KEY } from "../projects/api";
import type { CreateTargetBody, Paginated, Target, Uuid } from "../../types/api";

export const TARGETS_KEY = ["targets"] as const;

export function useTargetsQuery(projectId: Uuid | null) {
  const url = projectId
    ? `/api/targets/?project=${encodeURIComponent(projectId)}`
    : "/api/targets/";
  return useQuery({
    queryKey: [...TARGETS_KEY, { project: projectId }] as const,
    queryFn: () => http<Paginated<Target>>(url),
  });
}

export function useCreateTargetMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTargetBody) =>
      http<Target>("/api/targets/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: TARGETS_KEY });
      void client.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}
```

- [ ] **Step 4: Run + commit + /simplify**

```bash
npm run test -- src/features/targets/api
git add frontend/src/features/targets/api.ts frontend/src/features/targets/api.test.tsx frontend/src/types/api.ts
git commit -m "feat(frontend): add Targets API client"
```

---

### Task F: `TargetsList` page

**Files:**
- Create: `frontend/src/features/targets/TargetsList.tsx`
- Create: `frontend/src/features/targets/TargetsList.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { TargetsList } from "./TargetsList";

beforeEach(() => window.localStorage.clear());

function withProjectsAndTargets(targets: unknown[]) {
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "p1",
            name: "Local Lab",
            description: "",
            target_count: targets.length,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
        ],
      }),
    ),
    msw.get("/api/targets/", () =>
      HttpResponse.json({
        count: targets.length,
        next: null,
        previous: null,
        results: targets,
      }),
    ),
  );
}

describe("TargetsList", () => {
  it("prompts to select a project when none is current", () => {
    withProjectsAndTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(screen.getByText(/select a project/i)).toBeInTheDocument();
  });

  it("renders rows when a current project is set", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    withProjectsAndTargets([
      {
        id: "t1",
        project: "p1",
        base_url: "https://dvwa.cocode.dk",
        host: "dvwa.cocode.dk",
        ip: "89.167.63.167",
        status: "active",
        created_at: "2026-05-18T20:00:00.000000Z",
      },
    ]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText("https://dvwa.cocode.dk")).toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveAttribute("data-status", "active");
  });

  it("shows the empty state with an Add target action", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    withProjectsAndTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText(/no targets yet/i)).toBeInTheDocument();
  });

  it("has an Add target link in the page header that goes to /targets/new", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    withProjectsAndTargets([]);
    renderWithProviders(<TargetsList />, { route: "/targets" });
    const link = await screen.findByTestId("page-header-create");
    expect(link).toHaveAttribute("href", "/targets/new");
  });

  it("renders a callout with retry on fetch error", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "p1",
              name: "Lab",
              description: "",
              target_count: 0,
              scan_run_count: 0,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
      msw.get("/api/targets/", () => HttpResponse.error()),
    );
    renderWithProviders(<TargetsList />, { route: "/targets" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `TargetsList.tsx`**

```tsx
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { StatusBadge } from "../../components/StatusBadge";
import { useTargetsQuery } from "./api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import type { Target } from "../../types/api";

const columns: TableColumn<Target>[] = [
  { key: "base_url", header: "Base URL", cell: (r) => r.base_url },
  { key: "host", header: "Host", cell: (r) => r.host ?? "—" },
  { key: "ip", header: "IP", cell: (r) => r.ip ?? "—" },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge status={r.status} />,
  },
  {
    key: "created_at",
    header: "Created at",
    cell: (r) => r.created_at.slice(0, 10),
  },
];

export function TargetsList() {
  const { id: projectId } = useCurrentProject();
  const query = useTargetsQuery(projectId);
  const navigate = useNavigate();

  if (!projectId) {
    return (
      <>
        <PageHeader title="Targets" />
        <div className="mt-4">
          <Callout variant="info" title="Select a project first">
            Targets are scoped to the current project. Open the Projects page and set one as current.
          </Callout>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Targets"
        action={
          <ButtonLink to={ROUTES.targetsNew} data-testid="page-header-create">
            Add target
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
            Could not load targets.
          </Callout>
        ) : (
          <Table<Target>
            columns={columns}
            rows={query.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={query.isLoading}
            emptyState={
              <EmptyState
                message="No targets yet."
                action={{ label: "Add target", onClick: () => navigate(ROUTES.targetsNew) }}
              />
            }
          />
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 3: Add `ROUTES.targetsNew` to `src/app/routes.ts`**

```ts
export const ROUTES = {
  index: "/",
  projects: "/projects",
  projectsNew: "/projects/new",
  targets: "/targets",
  targetsNew: "/targets/new",
  stubs: "/stubs",
  scanRuns: "/scan-runs",
  findings: "/findings",
  evidence: "/evidence",
  settings: "/settings",
} as const;
```

- [ ] **Step 4: Run + commit + /simplify**

```bash
npm run test -- src/features/targets/TargetsList
git add frontend/src/features/targets/TargetsList.{tsx,test.tsx} frontend/src/app/routes.ts
git commit -m "feat(frontend): add TargetsList page"
```

---

### Task G: `AddTarget` form page

**Files:**
- Create: `frontend/src/features/targets/AddTarget.tsx`
- Create: `frontend/src/features/targets/AddTarget.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { AddTarget } from "./AddTarget";

beforeEach(() => window.localStorage.clear());

function LocationProbe() {
  return <span data-testid="loc">{useLocation().pathname}</span>;
}

function withProject() {
  window.localStorage.setItem("em.frontend.currentProjectId", "p1");
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "p1",
            name: "Lab",
            description: "",
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
        ],
      }),
    ),
  );
}

describe("AddTarget", () => {
  it("blocks when no current project is set", () => {
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    expect(screen.getByText(/select a project/i)).toBeInTheDocument();
  });

  it("validates base_url is required", async () => {
    withProject();
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await screen.findByLabelText(/Base URL/);
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText(/required/i)).toBeInTheDocument();
  });

  it("validates base_url must start with http:// or https://", async () => {
    withProject();
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(await screen.findByLabelText(/Base URL/), "dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText(/must start with http/i)).toBeInTheDocument();
  });

  it("submits and routes back to /targets on success", async () => {
    withProject();
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          {
            id: "t-new",
            project: "p1",
            base_url: "https://dvwa.cocode.dk",
            host: null,
            ip: null,
            status: "active",
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        ),
      ),
    );
    renderWithProviders(
      <>
        <AddTarget />
        <LocationProbe />
      </>,
      { route: "/targets/new" },
    );
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/targets"),
    );
  });

  it("renders non_field_errors above the form (e.g., uniqueness violation)", async () => {
    withProject();
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          { non_field_errors: ["target with this project and base url already exists."] },
          { status: 400 },
        ),
      ),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `AddTarget.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { FormField, TextInput } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { useCreateTargetMutation } from "./api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import { parseApiError } from "../../lib/parseApiError";
import { HttpError } from "../../lib/http";

export function AddTarget() {
  const { id: projectId } = useCurrentProject();
  const [baseUrl, setBaseUrl] = useState("");
  const [host, setHost] = useState("");
  const [ip, setIp] = useState("");
  const [localBaseUrlError, setLocalBaseUrlError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [bannerError, setBannerError] = useState<string | null>(null);
  const navigate = useNavigate();
  const mutation = useCreateTargetMutation();

  if (!projectId) {
    return (
      <>
        <PageHeader title="Add target" />
        <div className="mt-4">
          <Callout variant="info" title="Select a project first">
            Open the Projects page and set one as current before adding a target.
          </Callout>
        </div>
      </>
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!baseUrl.trim()) {
      setLocalBaseUrlError("base_url is required");
      return;
    }
    if (!/^https?:\/\//.test(baseUrl)) {
      setLocalBaseUrlError("base_url must start with http:// or https://");
      return;
    }
    setLocalBaseUrlError(null);
    setFieldErrors({});
    setBannerError(null);
    try {
      await mutation.mutateAsync({
        project: projectId!,
        base_url: baseUrl,
        host: host.trim() || null,
        ip: ip.trim() || null,
      });
      navigate(ROUTES.targets);
    } catch (err) {
      const parsed = await parseApiError(
        err instanceof HttpError ? err.response : err,
      );
      if (parsed.kind === "field") setFieldErrors(parsed.errors);
      else if (parsed.kind === "non_field") setBannerError(parsed.errors[0]);
      else if (parsed.kind === "detail") setBannerError(parsed.detail);
      else if (parsed.kind === "server") setBannerError("Something went wrong. Please try again.");
      else setBannerError("Backend unreachable.");
    }
  }

  return (
    <>
      <PageHeader title="Add target" />
      {bannerError && (
        <div className="mt-4">
          <Callout variant="error">{bannerError}</Callout>
        </div>
      )}
      <form onSubmit={onSubmit} noValidate className="mt-4 flex flex-col gap-4 max-w-lg">
        <FormField
          label="Base URL"
          htmlFor="base_url"
          required
          error={localBaseUrlError ?? fieldErrors.base_url?.[0]}
        >
          <TextInput
            id="base_url"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </FormField>
        <FormField label="Host" htmlFor="host" error={fieldErrors.host?.[0]}>
          <TextInput id="host" value={host} onChange={(e) => setHost(e.target.value)} />
        </FormField>
        <FormField label="IP" htmlFor="ip" error={fieldErrors.ip?.[0]}>
          <TextInput id="ip" value={ip} onChange={(e) => setIp(e.target.value)} />
        </FormField>
        <Button type="submit" loading={mutation.isPending}>
          Add target
        </Button>
      </form>
    </>
  );
}
```

- [ ] **Step 3: Run + commit + /simplify**

```bash
npm run test -- src/features/targets/AddTarget
git add frontend/src/features/targets/AddTarget.{tsx,test.tsx}
git commit -m "feat(frontend): add AddTarget form page"
```
