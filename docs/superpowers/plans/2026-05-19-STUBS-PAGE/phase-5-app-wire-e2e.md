# Phase 5 — App wiring + E2E + cleanup

Swap the `<ComingSoon name="Stubs" />` route for the real components and extend the slice-1 E2E so it walks `/stubs → /stubs/:slug → back to /stubs`. Also lifts the `STATUS_PALETTE` map to a shared module since both `StubsList` and `StubDetail` duplicate it.

---

### Task E: Wire routes + E2E + lift palette

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.e2e.test.tsx`
- Modify: `frontend/src/features/stubs/StubsList.tsx`
- Modify: `frontend/src/features/stubs/StubDetail.tsx`
- Create: `frontend/src/features/stubs/StatusBadge.tsx`
- Create: `frontend/src/features/stubs/StatusBadge.test.tsx`

- [ ] **Step 1: Lift `StatusBadge` to a shared module**

The `STATUS_PALETTE` + `StatusBadge` component is now duplicated in both `StubsList.tsx` and `StubDetail.tsx`. Lift to `frontend/src/features/stubs/StatusBadge.tsx`:

```tsx
import type { StubStatus } from "../../types/api";

const STATUS_PALETTE: Record<StubStatus, string> = {
  done: "bg-green-100 text-green-800",
  "in-progress": "bg-blue-100 text-blue-800",
  blocked: "bg-amber-100 text-amber-800",
  pending: "bg-gray-200 text-gray-700",
};

export function StatusBadge({ status }: { status: StubStatus }) {
  return (
    <span
      data-testid={`status-${status}`}
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_PALETTE[status]}`}
    >
      {status}
    </span>
  );
}
```

Add a tiny test pinning the four palette branches:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["done", /bg-green/],
    ["in-progress", /bg-blue/],
    ["blocked", /bg-amber/],
    ["pending", /bg-gray/],
  ] as const)("renders the %s palette", (status, pattern) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByTestId(`status-${status}`).className).toMatch(pattern);
  });
});
```

Update `StubsList.tsx` and `StubDetail.tsx` to `import { StatusBadge } from "./StatusBadge"` and drop their local copies.

- [ ] **Step 2: Edit `App.tsx`**

```tsx
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ROUTES } from "./app/routes";
import { ProjectsList } from "./features/projects/ProjectsList";
import { CreateProject } from "./features/projects/CreateProject";
import { TargetsList } from "./features/targets/TargetsList";
import { CreateTarget } from "./features/targets/CreateTarget";
import { StubsList } from "./features/stubs/StubsList";
import { StubDetail } from "./features/stubs/StubDetail";
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
        <Route path={ROUTES.stubs} element={<StubsList />} />
        <Route path={ROUTES.stubDetail} element={<StubDetail />} />
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

- [ ] **Step 3: Extend `App.e2e.test.tsx`**

Add a third `it(...)` inside the existing `describe("end-to-end slice 1", ...)`:

```tsx
it("walks the stubs list → detail → back flow", async () => {
  const stub = {
    slug: "1.1",
    phase: 1,
    spec: 1,
    phase_slug: "01-information-gathering",
    spec_slug: "framework-detection",
    title: "Framework detection",
    phase_title: "Information gathering",
    category: "Content discovery",
    status: "done" as const,
    fixture: "juice-shop",
    path: "01-information-gathering/01-framework-detection.md",
  };
  server.use(
    msw.get("/api/stubs/", () => HttpResponse.json([stub])),
    msw.get("/api/stubs/1.1/", () =>
      HttpResponse.json({
        ...stub,
        body: "# 1.1 Framework detection\n\nDetect the application framework.",
      }),
    ),
  );

  renderWithProviders(<App />, { route: "/stubs" });

  expect(await screen.findByText("Framework detection")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "1.1" }));
  await waitFor(() =>
    expect(screen.getByText(/Detect the application framework/)).toBeInTheDocument(),
  );
  expect(screen.getByText(/1\.1 · Framework detection/)).toBeInTheDocument();
  // Back-link to /stubs
  // (StubDetail's "Back to stubs" link only renders on 404; from the
  // happy path the operator uses the sidebar NavLink — assert that
  // returning via the sidebar lands on the populated list.)
  await userEvent.click(screen.getByRole("link", { name: "Stubs" }));
  await waitFor(() =>
    expect(screen.getByText("Framework detection")).toBeInTheDocument(),
  );
});
```

- [ ] **Step 4: Run the full test suite + coverage + build**

```bash
cd frontend && npm test -- --coverage && npm run build
```

Expected: every prior test still passes, the new e2e case passes, coverage stays 100/100/100/100, build green.

- [ ] **Step 5: Clean build artifacts**

```bash
rm -f frontend/tsconfig.node.tsbuildinfo frontend/tsconfig.tsbuildinfo frontend/vite.config.d.ts frontend/vite.config.js
rm -rf frontend/dist
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.e2e.test.tsx frontend/src/features/stubs/
git commit -m "feat(frontend): wire Stubs routes + lift StatusBadge + extend E2E"
```

- [ ] **Step 7: Final `/simplify` round**

Run `/simplify`. Iterate fix → commit → `/simplify` until clean.

- [ ] **Step 8: Single peer ping (slice completion)**

Per the chat-noise-floor rule, ping `agent-em-backend` exactly once now — with the final SHA list, "stubs slice 1 done", and the test summary. No per-phase pings were sent during execution.

- [ ] **Step 9: Notify operator for push auth**

`chat_notify` with the SHA list per the [Notify before push] rule. Do NOT push without explicit authorisation.

- [ ] **Step 10: Mark task complete**

Set TaskList task #103 to completed once the operator authorises push and the branch is up to date with origin.
