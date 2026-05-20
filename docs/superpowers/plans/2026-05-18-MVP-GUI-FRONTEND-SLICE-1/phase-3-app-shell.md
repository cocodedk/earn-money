# Phase 3 — App shell

Wraps the app in `QueryClientProvider` + `BrowserRouter`, defines the persistent `Layout` (sidebar + top bar + outlet), and a `ComingSoon` placeholder route.

---

### Task M: `Providers`

**Files:**
- Create: `frontend/src/app/Providers.tsx`
- Create: `frontend/src/app/Providers.test.tsx`
- Create: `frontend/src/app/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, Route, Routes } from "react-router-dom";
import { Providers } from "./Providers";

function QueryProbe() {
  const q = useQuery({ queryKey: ["x"], queryFn: () => 1 });
  return <div>q:{String(q.data ?? "...")}</div>;
}
function LocationProbe() {
  return <div>loc:{useLocation().pathname}</div>;
}

describe("Providers", () => {
  it("provides QueryClient and Router context", async () => {
    render(
      <Providers>
        <QueryProbe />
        <Routes>
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </Providers>,
    );
    expect(await screen.findByText("q:1")).toBeInTheDocument();
    expect(screen.getByText("loc:/")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `Providers.tsx`**

```tsx
import { ReactNode, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

export type ProvidersProps = { children: ReactNode };

export function Providers({ children }: ProvidersProps) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 3: `index.ts`**

```ts
export * from "./Providers";
```

- [ ] **Step 4: Run + commit**

```bash
cd frontend && npm run test -- src/app --coverage
git add frontend/src/app/
git commit -m "feat(frontend): add Providers (QueryClient + Router)"
```

---

### Task N: `Layout` (sidebar + top bar + outlet)

**Files:**
- Create: `frontend/src/app/Layout.tsx`
- Create: `frontend/src/app/Layout.module.css`
- Create: `frontend/src/app/Layout.test.tsx`
- Create: `frontend/src/app/nav.ts`
- Modify: `frontend/src/app/index.ts`

- [ ] **Step 1: Define nav items**

`frontend/src/app/nav.ts`:

```ts
export type NavItem = { label: string; to: string };

export const navItems: NavItem[] = [
  { label: "Projects", to: "/projects" },
  { label: "Targets", to: "/targets" },
  { label: "Stubs", to: "/stubs" },
  { label: "Scan Runs", to: "/scan-runs" },
  { label: "Findings", to: "/findings" },
  { label: "Evidence", to: "/evidence" },
  { label: "Settings", to: "/settings" },
];
```

- [ ] **Step 2: Test `Layout`**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./Layout";

function setup(initialRoute = "/projects") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/projects" element={<div>projects body</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("Layout", () => {
  it("renders the app name and all sidebar items", () => {
    setup();
    expect(screen.getByText("Cookbook scanner")).toBeInTheDocument();
    ["Projects", "Targets", "Stubs", "Scan Runs", "Findings", "Evidence", "Settings"].forEach(
      (label) => {
        expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
      },
    );
  });

  it("renders the outlet contents", () => {
    setup();
    expect(screen.getByText("projects body")).toBeInTheDocument();
  });

  it("marks the active route", () => {
    setup("/targets");
    // data-active lives on the inner span because NavLink's `isActive` is exposed there.
    expect(screen.getByText("Targets")).toHaveAttribute("data-active", "true");
  });
});
```

- [ ] **Step 3: Implement `Layout.tsx`**

```tsx
import { NavLink, Outlet } from "react-router-dom";
import styles from "./Layout.module.css";
import { navItems } from "./nav";

export function Layout() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>Cookbook scanner</div>
        <nav>
          <ul className={styles.navList}>
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={styles.navLink}
                  data-active={undefined}
                  end
                >
                  {({ isActive }) => (
                    <span data-active={isActive ? "true" : "false"}>
                      {item.label}
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topbarLeft}>{/* current project chip slot (Task V) */}</div>
          <div className={styles.topbarRight}>{/* connection pill slot (Task Q) */}</div>
        </header>
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

Note: the inner `<span data-active>` is the test handle. The top-bar slots are filled by `ConnectionPill` and `CurrentProjectChip` in Tasks Q and V.

- [ ] **Step 4: `Layout.module.css`**

```css
.shell {
  @apply h-full grid;
  grid-template-columns: 240px 1fr;
}
.sidebar {
  @apply bg-gray-50 border-r border-gray-200 flex flex-col py-4;
}
.brand {
  @apply px-4 pb-4 font-semibold text-sm;
}
.navList {
  @apply flex flex-col;
}
.navLink {
  @apply block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100;
}
.main {
  @apply flex flex-col min-w-0;
}
.topbar {
  @apply h-14 flex items-center justify-between px-6 border-b border-gray-200 bg-white;
}
.content {
  @apply flex-1 overflow-auto px-6 py-4;
}
.navLink span[data-active="true"] {
  @apply font-medium text-gray-900;
}
```

- [ ] **Step 5: Update `index.ts`**

```ts
export * from "./Providers";
export * from "./Layout";
export * from "./nav";
```

- [ ] **Step 6: Run + commit**

```bash
cd frontend && npm run test -- src/app/Layout --coverage
git add frontend/src/app/
git commit -m "feat(frontend): add Layout shell with sidebar nav"
```

---

### Task O: `ComingSoon` placeholder

**Files:**
- Create: `frontend/src/features/coming-soon/ComingSoon.tsx`
- Create: `frontend/src/features/coming-soon/ComingSoon.test.tsx`
- Create: `frontend/src/features/coming-soon/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComingSoon } from "./ComingSoon";

describe("ComingSoon", () => {
  it("renders the page name and the not-built-yet message", () => {
    render(<ComingSoon name="Targets" />);
    expect(screen.getByRole("heading", { name: "Targets" })).toBeInTheDocument();
    expect(screen.getByText(/not built yet/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement**

`frontend/src/features/coming-soon/ComingSoon.tsx`:

```tsx
import { PageHeader } from "../../components/PageHeader";

export type ComingSoonProps = { name: string };

export function ComingSoon({ name }: ComingSoonProps) {
  return (
    <>
      <PageHeader title={name} />
      <p className="mt-6 text-gray-600">Not built yet.</p>
    </>
  );
}
```

- [ ] **Step 3: `index.ts`**

```ts
export * from "./ComingSoon";
```

- [ ] **Step 4: Run + commit**

```bash
cd frontend && npm run test -- src/features/coming-soon --coverage
git add frontend/src/features/coming-soon/
git commit -m "feat(frontend): add ComingSoon placeholder page"
```
