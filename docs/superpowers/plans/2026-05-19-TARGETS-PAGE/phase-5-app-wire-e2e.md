# Phase 5 — App wiring + E2E

Swap the two `<ComingSoon name="Targets" />` routes in `App.tsx` for the real components and extend the slice-1 E2E happy path so it walks `Projects → Create project → Targets → Create target → Targets`.

---

### Task E: Wire routes and extend E2E

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.e2e.test.tsx`

- [ ] **Step 1: Edit `App.tsx`**

Replace the file with:

```tsx
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ROUTES } from "./app/routes";
import { ProjectsList } from "./features/projects/ProjectsList";
import { CreateProject } from "./features/projects/CreateProject";
import { TargetsList } from "./features/targets/TargetsList";
import { CreateTarget } from "./features/targets/CreateTarget";
import { ComingSoon } from "./features/coming-soon";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to={ROUTES.projects} replace />} />
        <Route path={ROUTES.projects} element={<ProjectsList />} />
        <Route path={ROUTES.projectsNew} element={<CreateProject />} />
        <Route path={ROUTES.targets} element={<TargetsList />} />
        <Route path={ROUTES.targetsNew} element={<CreateTarget />} />
        <Route path={ROUTES.stubs} element={<ComingSoon name="Stubs" />} />
        <Route path={ROUTES.scanRuns} element={<ComingSoon name="Scan Runs" />} />
        <Route path={ROUTES.findings} element={<ComingSoon name="Findings" />} />
        <Route path={ROUTES.evidence} element={<ComingSoon name="Evidence" />} />
        <Route path={ROUTES.settings} element={<ComingSoon name="Settings" />} />
        <Route path="*" element={<ComingSoon name="Not found" />} />
      </Route>
    </Routes>
  );
}
```

Two lines changed: targets and targetsNew routes now point at the real components.

- [ ] **Step 2: Extend the E2E test**

Edit `frontend/src/App.e2e.test.tsx`. Add a second `it(...)` block inside the existing `describe("end-to-end slice 1", ...)`:

```tsx
it("creates a target after a project and lands on a populated targets list", async () => {
  let storedProject: { id: string; name: string } | null = null;
  let storedTarget:
    | {
        id: string;
        project: string;
        base_url: string;
        host: string;
        ip: string | null;
      }
    | null = null;
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({
        count: storedProject ? 1 : 0,
        next: null,
        previous: null,
        results: storedProject
          ? [
              {
                id: storedProject.id,
                name: storedProject.name,
                description: "",
                target_count: storedTarget ? 1 : 0,
                scan_run_count: 0,
                created_at: "2026-05-19T08:00:00.000000Z",
              },
            ]
          : [],
      }),
    ),
    msw.post("/api/projects/", async ({ request }) => {
      const body = (await request.json()) as { name: string };
      storedProject = { id: "p-1", name: body.name };
      return HttpResponse.json(
        {
          id: "p-1",
          name: body.name,
          description: "",
          target_count: 0,
          scan_run_count: 0,
          created_at: "2026-05-19T08:00:00.000000Z",
        },
        { status: 201 },
      );
    }),
    msw.get("/api/targets/", () =>
      HttpResponse.json({
        count: storedTarget ? 1 : 0,
        next: null,
        previous: null,
        results: storedTarget
          ? [
              {
                ...storedTarget,
                status: "active",
                created_at: "2026-05-19T08:00:00.000000Z",
                updated_at: "2026-05-19T08:00:00.000000Z",
              },
            ]
          : [],
      }),
    ),
    msw.post("/api/targets/", async ({ request }) => {
      const body = (await request.json()) as {
        project: string;
        base_url: string;
      };
      storedTarget = {
        id: "t-1",
        project: body.project,
        base_url: body.base_url,
        host: "dvwa.cocode.dk",
        ip: null,
      };
      return HttpResponse.json(
        {
          ...storedTarget,
          status: "active",
          created_at: "2026-05-19T08:00:00.000000Z",
          updated_at: "2026-05-19T08:00:00.000000Z",
        },
        { status: 201 },
      );
    }),
  );

  renderWithProviders(<App />, { route: "/projects" });

  // Create the project first
  await userEvent.click(await screen.findByTestId("page-header-create"));
  await userEvent.type(screen.getByLabelText(/Name/), "Local Lab");
  await userEvent.type(screen.getByLabelText(/Description/), "lab");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  await waitFor(() => expect(screen.getByText("Local Lab")).toBeInTheDocument());

  // Navigate to the Targets tab
  await userEvent.click(screen.getByRole("link", { name: /^Targets/ }));
  expect(await screen.findByText("No targets yet.")).toBeInTheDocument();

  // Create a target
  await userEvent.click(screen.getByTestId("page-header-create"));
  await userEvent.selectOptions(
    await screen.findByLabelText(/Project/),
    "Local Lab",
  );
  await userEvent.type(
    screen.getByLabelText(/Base URL/),
    "https://dvwa.cocode.dk",
  );
  await userEvent.click(screen.getByRole("button", { name: "Create target" }));

  await waitFor(() => {
    expect(screen.getByText("https://dvwa.cocode.dk")).toBeInTheDocument();
  });
  expect(screen.getByText("dvwa.cocode.dk")).toBeInTheDocument();
  expect(screen.getByText("Local Lab")).toBeInTheDocument();
});
```

The link selector `/^Targets/` matches the sidebar `NavLink` label exactly (avoids ambiguity with the page header "Targets" heading once rendered — both contain the word, but the NavLink is the only one wrapped in an `<a>` with role `link`).

- [ ] **Step 3: Run the full test suite**

```bash
cd frontend && npm run test -- --coverage
```

Expected: every prior test still passes, both E2E cases pass, coverage stays at 100/100/100/100 (the project's `vitest.config.ts` thresholds will fail the run otherwise).

- [ ] **Step 4: Run typecheck, lint, build**

```bash
cd frontend && npm run typecheck && npm run lint && npm run build
```

Expected: all three green. If `npm run build` fails on the `@apply` directives, the styling utilities haven't changed — re-run `npm install` and retry; this is the same harmless dev-mode flake as in slice 1.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.e2e.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): wire Targets routes + extend E2E happy path

Swaps the two <ComingSoon name="Targets" /> routes for the real
TargetsList and CreateTarget components. Extends App.e2e.test with
a second case that creates a project, then a target, asserting the
project-name join resolves on the targets list.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Run `/simplify` and iterate**

```bash
/simplify
```

Fix → commit → `/simplify` until clean.

- [ ] **Step 7: Manual smoke test against the live backend**

If `docker compose up` is running locally:

1. Open `http://localhost/targets`.
2. Click "Create target".
3. Pick "Local Lab" (or whichever project exists).
4. Type `https://dvwa.cocode.dk` in Base URL.
5. Leave Host and IP blank.
6. Submit.
7. Land on `/targets`. Row shows base_url, host `dvwa.cocode.dk`, ip `—`, project name resolved, status `active`.

If anything fails, fix before claiming done.

- [ ] **Step 8: Final peer ping + request push auth**

Notify `agent-em-backend` on the bus with the final commit list:

> "Targets slice complete on refactor/archive-v1. Commits: <SHA list from `git log origin/main..HEAD -- frontend/src/features/targets frontend/src/App.tsx`>. 100% coverage held; manual smoke against dvwa.cocode.dk green. Asking operator for push auth."

Then `chat_notify` the operator (do NOT push without authorisation — [Notify before push](../../../../.claude-personal/projects/-home-cocodedk-0-projects-earn-money/memory/feedback_notify_before_push.md)).

- [ ] **Step 9: Mark task complete**

Once operator authorises push and the branch is up to date with origin, mark TaskList task #98 complete.
