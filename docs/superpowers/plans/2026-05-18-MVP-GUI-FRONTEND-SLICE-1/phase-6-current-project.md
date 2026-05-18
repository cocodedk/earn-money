# Phase 6 — Current project (frontend-only)

Slice-1 wires the `useCurrentProject` hook and the top-bar `CurrentProjectChip`. Backend has no concept of "current project"; this is purely a `localStorage` convenience for the operator.

---

### Task U: `useCurrentProject`

**Files:**
- Create: `frontend/src/lib/useCurrentProject.ts`
- Create: `frontend/src/lib/useCurrentProject.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../test/server";
import { useCurrentProject } from "./useCurrentProject";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("useCurrentProject", () => {
  it("starts null when localStorage is empty", () => {
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    expect(result.current.id).toBeNull();
  });

  it("persists setId to localStorage and reflects in next read", () => {
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    act(() => result.current.setId("u-1"));
    expect(window.localStorage.getItem("em.frontend.currentProjectId")).toBe("u-1");
    expect(result.current.id).toBe("u-1");
  });

  it("resolves the project from the cached list", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "u-1",
              name: "Local Lab",
              description: "",
              target_count: 0,
              scan_run_count: 0,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    window.localStorage.setItem("em.frontend.currentProjectId", "u-1");
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    await waitFor(() => expect(result.current.project?.name).toBe("Local Lab"));
  });

  it("clears the id when the project no longer exists", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    window.localStorage.setItem("em.frontend.currentProjectId", "u-gone");
    const { result } = renderHook(() => useCurrentProject(), { wrapper });
    await waitFor(() => expect(result.current.id).toBeNull());
    expect(window.localStorage.getItem("em.frontend.currentProjectId")).toBeNull();
  });
});
```

- [ ] **Step 2: Implement**

`frontend/src/lib/useCurrentProject.ts`:

```ts
import { useEffect, useState } from "react";
import { useProjectsQuery } from "../features/projects/api";
import type { Project } from "../types/api";

const KEY = "em.frontend.currentProjectId";

export function useCurrentProject() {
  const [id, setIdState] = useState<string | null>(
    () => window.localStorage.getItem(KEY),
  );

  function setId(next: string | null) {
    if (next === null) {
      window.localStorage.removeItem(KEY);
    } else {
      window.localStorage.setItem(KEY, next);
    }
    setIdState(next);
  }

  const query = useProjectsQuery();
  const project: Project | null =
    id && query.data ? query.data.results.find((p) => p.id === id) ?? null : null;

  useEffect(() => {
    if (id && query.data && !project) {
      setId(null);
    }
  }, [id, query.data, project]);

  return { id, setId, project };
}
```

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm run test -- src/lib/useCurrentProject --coverage
git add frontend/src/lib/useCurrentProject.ts frontend/src/lib/useCurrentProject.test.tsx
git commit -m "feat(frontend): add useCurrentProject (localStorage-backed)"
```

---

### Task V: `CurrentProjectChip`

**Files:**
- Create: `frontend/src/components/CurrentProjectChip/CurrentProjectChip.tsx`
- Create: `frontend/src/components/CurrentProjectChip/CurrentProjectChip.module.css`
- Create: `frontend/src/components/CurrentProjectChip/CurrentProjectChip.test.tsx`
- Create: `frontend/src/components/CurrentProjectChip/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { CurrentProjectChip } from "./CurrentProjectChip";

beforeEach(() => window.localStorage.clear());

function withOneProject() {
  server.use(
    msw.get("/api/projects/", () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "u-1",
            name: "Local Lab",
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

describe("CurrentProjectChip", () => {
  it("renders the no-selection state when localStorage is empty", () => {
    withOneProject();
    renderWithProviders(<CurrentProjectChip />, { route: "/" });
    expect(screen.getByText(/no project selected/i)).toBeInTheDocument();
  });

  it("renders the resolved project name", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "u-1");
    withOneProject();
    renderWithProviders(<CurrentProjectChip />, { route: "/" });
    await waitFor(() =>
      expect(screen.getByTestId("current-project-chip")).toHaveTextContent("Local Lab"),
    );
  });

  it("has a switch link to /projects", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "u-1");
    withOneProject();
    renderWithProviders(<CurrentProjectChip />, { route: "/" });
    const link = await screen.findByTestId("current-project-switch");
    expect(link).toHaveAttribute("href", "/projects");
    await userEvent.click(link);
  });
});
```

- [ ] **Step 2: Implement**

`frontend/src/components/CurrentProjectChip/CurrentProjectChip.tsx`:

```tsx
import { Link } from "react-router-dom";
import styles from "./CurrentProjectChip.module.css";
import { useCurrentProject } from "../../lib/useCurrentProject";

export function CurrentProjectChip() {
  const { project } = useCurrentProject();
  return (
    <div className={styles.chip} data-testid="current-project-chip">
      <span>{project ? project.name : "(no project selected)"}</span>
      <Link
        to="/projects"
        data-testid="current-project-switch"
        className={styles.switch}
      >
        switch
      </Link>
    </div>
  );
}
```

- [ ] **Step 3: `CurrentProjectChip.module.css`**

```css
.chip {
  @apply inline-flex items-center gap-2 text-sm text-gray-700;
}
.switch {
  @apply text-blue-700 hover:underline;
}
```

- [ ] **Step 4: `index.ts`**

```ts
export * from "./CurrentProjectChip";
```

- [ ] **Step 5: Run + commit**

```bash
cd frontend && npm run test -- src/components/CurrentProjectChip --coverage
git add frontend/src/components/CurrentProjectChip/
git commit -m "feat(frontend): add CurrentProjectChip wired to useCurrentProject"
```
