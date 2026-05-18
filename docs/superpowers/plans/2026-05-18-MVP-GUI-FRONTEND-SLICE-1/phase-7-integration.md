# Phase 7 — Integration

Replace the health-check `App.tsx` with the real router + layout, wire `ConnectionPill` and `CurrentProjectChip` into the top bar, and ship one end-to-end test that exercises the entire slice through MSW.

---

### Task W: Wire `App.tsx`

**Files:**
- Replace: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/app/Layout.tsx` (fill the top-bar slots)

- [ ] **Step 1: Update `Layout.tsx` to render the slots**

Replace the two empty slot comments in `Layout.tsx` with actual components:

```tsx
import { CurrentProjectChip } from "../components/CurrentProjectChip";
import { ConnectionPill } from "../components/ConnectionPill";

// inside the topbar JSX:
<div className={styles.topbarLeft}>
  <CurrentProjectChip />
</div>
<div className={styles.topbarRight}>
  <ConnectionPill />
</div>
```

- [ ] **Step 2: Add a router test to `Layout.test.tsx`** to keep the regression net tight

Append a third `it` to the existing `Layout` describe:

```tsx
it("renders the connection pill and current-project chip in the top bar", async () => {
  // server has the default /api/health/ handler from src/test/handlers.ts
  setup();
  expect(await screen.findByTestId("connection-pill")).toBeInTheDocument();
  expect(screen.getByTestId("current-project-chip")).toBeInTheDocument();
});
```

Note: `setup()` already provides a `MemoryRouter`, but the test now also needs the `QueryClientProvider`. Refactor `setup()` to use `renderWithProviders` and pass an `outlet` for `/projects`:

```tsx
function setup(initialRoute = "/projects") {
  return renderWithProviders(
    <Routes>
      <Route element={<Layout />}>
        <Route path="/projects" element={<div>projects body</div>} />
      </Route>
    </Routes>,
    { route: initialRoute },
  );
}
```

- [ ] **Step 3: Replace `App.tsx`**

```tsx
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ProjectsList } from "./features/projects/ProjectsList";
import { CreateProject } from "./features/projects/CreateProject";
import { ComingSoon } from "./features/coming-soon";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectsList />} />
        <Route path="/projects/new" element={<CreateProject />} />
        <Route path="/targets" element={<ComingSoon name="Targets" />} />
        <Route path="/stubs" element={<ComingSoon name="Stubs" />} />
        <Route path="/scan-runs" element={<ComingSoon name="Scan Runs" />} />
        <Route path="/findings" element={<ComingSoon name="Findings" />} />
        <Route path="/evidence" element={<ComingSoon name="Evidence" />} />
        <Route path="/settings" element={<ComingSoon name="Settings" />} />
        <Route path="*" element={<ComingSoon name="Not found" />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 4: Update `main.tsx`** to wrap `App` with `Providers`:

```tsx
import "./styles/global.css";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { Providers } from "./app/Providers";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Providers>
      <App />
    </Providers>
  </React.StrictMode>,
);
```

- [ ] **Step 5: Run full test suite**

```bash
cd frontend && npm run test -- --coverage
```

Expected: all tests pass; coverage 100/100/100/100 on `src/**/*.{ts,tsx}` (minus the configured exclusions).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/main.tsx frontend/src/app/Layout.tsx frontend/src/app/Layout.test.tsx
git commit -m "feat(frontend): wire App.tsx with router + Layout slots filled"
```

---

### Task X: Sidebar active-route highlight regression test

**Files:**
- Modify: `frontend/src/app/Layout.test.tsx`

- [ ] **Step 1: Add a route-change test**

Append to `Layout` describe:

```tsx
it("moves the active marker when the route changes", async () => {
  // Use a fresh memory router with two routes registered.
  const { rerender } = renderWithProviders(
    <Routes>
      <Route element={<Layout />}>
        <Route path="/projects" element={<div>p</div>} />
        <Route path="/targets" element={<div>t</div>} />
      </Route>
    </Routes>,
    { route: "/projects" },
  );
  expect(screen.getByText("Projects")).toHaveAttribute("data-active", "true");
  rerender(
    <Routes>
      <Route element={<Layout />}>
        <Route path="/projects" element={<div>p</div>} />
        <Route path="/targets" element={<div>t</div>} />
      </Route>
    </Routes>,
  );
  // navigate via user event to /targets
  await userEvent.click(screen.getByText("Targets"));
  expect(screen.getByText("Targets")).toHaveAttribute("data-active", "true");
});
```

- [ ] **Step 2: Run + commit**

```bash
cd frontend && npm run test -- src/app/Layout
git add frontend/src/app/Layout.test.tsx
git commit -m "test(frontend): assert sidebar active highlight follows route"
```

---

### Task Y: End-to-end happy path

A single Vitest test that exercises the entire slice through MSW: load app, see empty projects, click create, fill form, submit, see new row.

**Files:**
- Create: `frontend/src/App.e2e.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import App from "./App";

beforeEach(() => window.localStorage.clear());

describe("end-to-end slice 1", () => {
  it("creates a project and lands on a populated list", async () => {
    let stored: { name: string; description: string } | null = null;
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: stored ? 1 : 0,
          next: null,
          previous: null,
          results: stored
            ? [
                {
                  id: "u-1",
                  ...stored,
                  target_count: 0,
                  scan_run_count: 0,
                  created_at: "2026-05-18T20:00:00.000000Z",
                },
              ]
            : [],
        }),
      ),
      msw.post("/api/projects/", async ({ request }) => {
        stored = (await request.json()) as typeof stored;
        return HttpResponse.json(
          {
            id: "u-1",
            ...stored,
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<App />, { route: "/projects" });

    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("page-header-create"));
    await userEvent.type(screen.getByLabelText(/Name/), "Local Lab");
    await userEvent.type(screen.getByLabelText(/Description/), "lab");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));

    await waitFor(() => {
      expect(screen.getByText("Local Lab")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run + commit**

```bash
cd frontend && npm run test -- src/App.e2e.test
git add frontend/src/App.e2e.test.tsx
git commit -m "test(frontend): add slice-1 end-to-end happy path via MSW"
```

---

## Final pass

- [ ] **Step 1: Full test + coverage run**

```bash
cd frontend && npm run test:coverage
```

Expected: 100/100/100/100 on every file matching the include glob.

- [ ] **Step 2: Build production bundle**

```bash
cd frontend && npx vite build
```

Expected: build succeeds, no TS errors, no unused imports.

- [ ] **Step 3: Bring up the compose stack**

```bash
docker compose up --build
```

Open `http://localhost/`. Expected: redirected to `/projects`, sidebar present with 7 nav items, top bar shows the connection pill (green if backend up). Create a project, see it appear in the list.

- [ ] **Step 4: Notify peer that slice 1 is green**

Use `chat_message_agent` to ping `agent-em-backend` with the commit range and ask them to verify the contract against their `ProjectsModelViewSet`.

- [ ] **Step 5: Acceptance**

Slice 1 is complete when:
- The full test run is green with 100% coverage.
- The compose stack works end-to-end without errors in the browser console.
- Both agents have confirmed the contract behaves as `11-api.md` specifies.
