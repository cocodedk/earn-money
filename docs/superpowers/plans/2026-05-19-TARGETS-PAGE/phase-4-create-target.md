# Phase 4 — CreateTarget page

The form at `/targets/new`. The largest phase: 12 test cases covering the validation pipeline codex:rescue insisted on. Validation runs trim → scheme+authority regex → WHATWG URL parse backstop. Project select states (loading/error/empty/loaded) are wired explicitly.

---

### Task D: `CreateTarget` page

**Files:**
- Create: `frontend/src/features/targets/CreateTarget.tsx`
- Create: `frontend/src/features/targets/CreateTarget.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/targets/CreateTarget.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { CreateTarget } from "./CreateTarget";

const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 0,
  scan_run_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
};

function withProjects(rows: unknown[]) {
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({ count: rows.length, next: null, previous: null, results: rows }),
    ),
  );
}

function trackPostCount() {
  let count = 0;
  server.use(
    msw.post("/api/targets/", () => {
      count += 1;
      return HttpResponse.json({}, { status: 201 });
    }),
  );
  return () => count;
}

function LocationProbe() {
  return <span data-testid="loc">{useLocation().pathname}</span>;
}

async function pickProject(name = "Local Lab") {
  const select = await screen.findByLabelText(/Project/);
  await userEvent.selectOptions(select, name);
}

async function typeBaseUrl(value: string) {
  await userEvent.type(screen.getByLabelText(/Base URL/), value);
}

describe("CreateTarget — happy paths", () => {
  it("submits and routes back to /targets on success (all fields)", async () => {
    withProjects([PROJECT]);
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          {
            id: "t-new",
            project: "p-1",
            base_url: "https://dvwa.cocode.dk",
            host: "dvwa.cocode.dk",
            ip: "127.0.0.1",
            status: "active",
            created_at: "2026-05-19T08:00:00.000000Z",
            updated_at: "2026-05-19T08:00:00.000000Z",
          },
          { status: 201 },
        ),
      ),
    );
    renderWithProviders(
      <>
        <CreateTarget />
        <LocationProbe />
      </>,
      { route: "/targets/new" },
    );
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.type(screen.getByLabelText(/^Host/), "dvwa.cocode.dk");
    await userEvent.type(screen.getByLabelText(/^IP/), "127.0.0.1");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/targets"),
    );
  });

  it("submits with blank host and ip; backend echoes derived host", async () => {
    withProjects([PROJECT]);
    let received: { host?: string; ip?: string | null } = {};
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = (await request.json()) as typeof received;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    await waitFor(() => expect(received).not.toEqual({}));
    expect(received.host).toBeUndefined();
    expect(received.ip).toBeUndefined();
  });
});

describe("CreateTarget — projects-query branches", () => {
  it("disables project select while projects are loading", async () => {
    server.use(
      msw.get("/api/projects/", async () => {
        await new Promise((r) => setTimeout(r, 5000));
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    const select = await screen.findByLabelText(/Project/);
    expect(select).toBeDisabled();
    expect(screen.getByText(/Loading projects/i)).toBeInTheDocument();
  });

  it("shows an error callout when the projects query fails", async () => {
    server.use(msw.get("/api/projects/", () => HttpResponse.error()));
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    expect(await screen.findByText(/could not load projects/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Project/)).toBeDisabled();
  });

  it("links to /projects/new when the projects list is empty", async () => {
    withProjects([]);
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    const link = await screen.findByRole("link", { name: /create a project first/i });
    expect(link).toHaveAttribute("href", "/projects/new");
    expect(screen.getByLabelText(/Project/)).toBeDisabled();
  });
});

describe("CreateTarget — base_url validation (no network call)", () => {
  it("rejects empty base_url", async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(await screen.findByText(/base_url is required/i)).toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it("rejects base_url without scheme", async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("not-a-url");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/must start with http:\/\/ or https:\/\//i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it('rejects "https://" with empty authority', async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/must start with http:\/\/ or https:\/\//i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it('rejects "https:// " with whitespace authority', async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https:// ");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/must start with http:\/\/ or https:\/\//i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it('rejects "https:///path" with empty authority', async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https:///path");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/must start with http:\/\/ or https:\/\//i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });
});

describe("CreateTarget — server errors", () => {
  it("renders server field error on the project field", async () => {
    withProjects([PROJECT]);
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          { project: ["Invalid project."] },
          { status: 400 },
        ),
      ),
    );
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(await screen.findByText("Invalid project.")).toBeInTheDocument();
  });

  it("renders backend-unreachable banner on network failure", async () => {
    withProjects([PROJECT]);
    server.use(msw.post("/api/targets/", () => HttpResponse.error()));
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });
});
```

Total: 12 tests. Each `it(...)` is self-contained with its own MSW handler set; the existing `afterEach(server.resetHandlers())` from `test/setup.ts` cleans state between cases.

- [ ] **Step 2: Run the test — it must fail**

```bash
cd frontend && npm run test -- src/features/targets/CreateTarget
```

Expected: module-not-found error pointing at `./CreateTarget`.

- [ ] **Step 3: Implement `CreateTarget.tsx`**

Create `frontend/src/features/targets/CreateTarget.tsx`:

```tsx
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { FormField, TextInput } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { useProjectsQuery } from "../projects/api";
import { useCreateTargetMutation } from "./api";
import { parseApiError } from "../../lib/parseApiError";
import { HttpError } from "../../lib/http";
import type { CreateTargetBody } from "../../types/api";

const SCHEME_AUTHORITY = /^https?:\/\/[^/\s]+/i;

type LocalError = string | null;

function validateBaseUrl(raw: string): LocalError {
  const value = raw.trim();
  if (!value) return "base_url is required";
  if (!SCHEME_AUTHORITY.test(value)) {
    return "base_url must start with http:// or https:// and include a host";
  }
  try {
    const parsed = new URL(value);
    if (parsed.hostname === "") {
      return "Enter a valid URL like https://example.com";
    }
  } catch {
    return "Enter a valid URL like https://example.com";
  }
  return null;
}

export function CreateTarget() {
  const projects = useProjectsQuery();
  const mutation = useCreateTargetMutation();
  const navigate = useNavigate();

  const [projectId, setProjectId] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [host, setHost] = useState("");
  const [ip, setIp] = useState("");
  const [localBaseUrlError, setLocalBaseUrlError] = useState<LocalError>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [bannerError, setBannerError] = useState<string | null>(null);

  const isProjectsEmpty =
    projects.isSuccess && (projects.data?.results.length ?? 0) === 0;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const urlError = validateBaseUrl(baseUrl);
    setLocalBaseUrlError(urlError);
    if (urlError) return;
    setFieldErrors({});
    setBannerError(null);
    const body: CreateTargetBody = {
      project: projectId,
      base_url: baseUrl.trim(),
      ...(host.trim() ? { host: host.trim() } : {}),
      ...(ip.trim() ? { ip: ip.trim() } : {}),
    };
    try {
      await mutation.mutateAsync(body);
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

  const projectSelectDisabled =
    projects.isLoading || projects.isError || isProjectsEmpty;

  return (
    <>
      <PageHeader title="Create target" />
      {bannerError && (
        <div className="mt-4">
          <Callout variant="error">{bannerError}</Callout>
        </div>
      )}
      {projects.isError && (
        <div className="mt-4">
          <Callout variant="error">Could not load projects.</Callout>
        </div>
      )}
      {isProjectsEmpty && (
        <div className="mt-4">
          <Callout variant="info">
            <Link to={ROUTES.projectsNew}>Create a project first.</Link>
          </Callout>
        </div>
      )}
      <form onSubmit={onSubmit} noValidate className="mt-4 flex flex-col gap-4 max-w-lg">
        <FormField
          label="Project"
          htmlFor="project"
          required
          error={fieldErrors.project?.[0]}
        >
          <select
            id="project"
            value={projectId}
            disabled={projectSelectDisabled}
            onChange={(e) => setProjectId(e.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">
              {projects.isLoading ? "Loading projects…" : "Select a project…"}
            </option>
            {(projects.data?.results ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </FormField>
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
        <FormField
          label="Host"
          htmlFor="host"
          error={fieldErrors.host?.[0]}
        >
          <TextInput
            id="host"
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="Leave blank to auto-derive from base URL"
          />
        </FormField>
        <FormField
          label="IP"
          htmlFor="ip"
          error={fieldErrors.ip?.[0]}
        >
          <TextInput
            id="ip"
            value={ip}
            onChange={(e) => setIp(e.target.value)}
            placeholder="Leave blank if unknown"
          />
        </FormField>
        <Button type="submit" loading={mutation.isPending}>
          Create target
        </Button>
      </form>
    </>
  );
}
```

The file lands at ~140 lines including blank lines — under the 200-line cap. The validation regex `^https?:\/\/[^/\s]+` requires a scheme followed by at least one non-slash, non-whitespace authority character. The `new URL()` backstop catches edge cases the regex doesn't (e.g. URL-parser-specific normalisation).

- [ ] **Step 4: Run the test — it must pass**

```bash
cd frontend && npm run test -- src/features/targets/CreateTarget --coverage
```

Expected: all 12 tests pass; coverage 100% on `CreateTarget.tsx`.

If `eslint` complains about the unused `vi` import in the test file, remove it. The skeleton kept it for parity with the Projects analog; this slice doesn't need a spy.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/targets/CreateTarget.tsx frontend/src/features/targets/CreateTarget.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add CreateTarget page with tight base_url validation

Validation pipeline (trim → scheme+authority regex → URL parse backstop)
rejects "https://", "https:// ", "https:///path", and other empty- or
whitespace-authority inputs without firing a network call. Tests pin
each branch (12 cases). Project select disabled during projects-query
loading / error / empty states; empty list shows a link to /projects/new.
Server field errors flow through parseApiError exactly like CreateProject.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Run `/simplify` and iterate**

```bash
/simplify
```

This is the largest commit in the slice — expect a few fixup rounds. Iterate until clean.

- [ ] **Step 7: Notify peer**

Send a chat-mcp ping to `agent-em-backend`:

> "CreateTarget (phase 4) green: 12 tests + 100% coverage including the codex-vetted malformed-host rejections. Moving to App.tsx wiring + E2E (phase 5)."
