# Phase 4 — Health pill

`useConnectionStatus` polls `/api/health/` every 30s; `ConnectionPill` consumes it and shows a green / red dot in the top bar.

---

### Task P: `useConnectionStatus`

**Files:**
- Create: `frontend/src/lib/useConnectionStatus.ts`
- Create: `frontend/src/lib/useConnectionStatus.test.tsx`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../test/server";
import { useConnectionStatus } from "./useConnectionStatus";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useConnectionStatus", () => {
  it("returns connected when /api/health/ is reachable and db is true", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({ status: "ok", db: true }),
      ),
    );
    const { result } = renderHook(() => useConnectionStatus(), { wrapper });
    await waitFor(() => expect(result.current.connected).toBe(true));
  });

  it("returns disconnected when /api/health/ fails", async () => {
    server.use(msw.get("/api/health/", () => HttpResponse.error()));
    const { result } = renderHook(() => useConnectionStatus(), { wrapper });
    await waitFor(() => expect(result.current.connected).toBe(false));
  });

  it("returns disconnected when db: false", async () => {
    server.use(
      msw.get("/api/health/", () =>
        HttpResponse.json({ status: "degraded", db: false }),
      ),
    );
    const { result } = renderHook(() => useConnectionStatus(), { wrapper });
    await waitFor(() => expect(result.current.connected).toBe(false));
  });
});
```

- [ ] **Step 2: Implement**

`frontend/src/lib/useConnectionStatus.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { http } from "./http";
import type { HealthResponse } from "../types/api";

export function useConnectionStatus() {
  const query = useQuery({
    queryKey: ["health"],
    queryFn: () => http<HealthResponse>("/api/health/"),
    refetchInterval: 30_000,
    staleTime: 0,
  });
  const connected = Boolean(query.data && query.data.status === "ok" && query.data.db);
  return { connected, isLoading: query.isLoading };
}
```

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm run test -- src/lib/useConnectionStatus --coverage
git add frontend/src/lib/useConnectionStatus.ts frontend/src/lib/useConnectionStatus.test.tsx
git commit -m "feat(frontend): add useConnectionStatus hook polling /api/health/"
```

---

### Task Q: `ConnectionPill`

**Files:**
- Create: `frontend/src/components/ConnectionPill/ConnectionPill.tsx`
- Create: `frontend/src/components/ConnectionPill/ConnectionPill.module.css`
- Create: `frontend/src/components/ConnectionPill/ConnectionPill.test.tsx`
- Create: `frontend/src/components/ConnectionPill/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ConnectionPill } from "./ConnectionPill";

function renderPill() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConnectionPill />
    </QueryClientProvider>,
  );
}

describe("ConnectionPill", () => {
  it("shows Connected when /api/health/ is healthy", async () => {
    server.use(msw.get("/api/health/", () => HttpResponse.json({ status: "ok", db: true })));
    renderPill();
    await waitFor(() => {
      expect(screen.getByTestId("connection-pill")).toHaveAttribute(
        "data-connected",
        "true",
      );
    });
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows Disconnected on health failure", async () => {
    server.use(msw.get("/api/health/", () => HttpResponse.error()));
    renderPill();
    await waitFor(() => {
      expect(screen.getByTestId("connection-pill")).toHaveAttribute(
        "data-connected",
        "false",
      );
    });
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement**

```tsx
import styles from "./ConnectionPill.module.css";
import { useConnectionStatus } from "../../lib/useConnectionStatus";

export function ConnectionPill() {
  const { connected } = useConnectionStatus();
  return (
    <div
      className={styles.pill}
      data-testid="connection-pill"
      data-connected={connected ? "true" : "false"}
    >
      <span className={styles.dot} aria-hidden="true" />
      <span>{connected ? "Connected" : "Disconnected"}</span>
    </div>
  );
}
```

- [ ] **Step 3: `ConnectionPill.module.css`**

```css
.pill {
  @apply inline-flex items-center gap-2 text-sm text-gray-700;
}
.dot {
  @apply h-2 w-2 rounded-full bg-gray-400 transition-opacity duration-200;
}
.pill[data-connected="true"] .dot {
  @apply bg-green-500;
}
.pill[data-connected="false"] .dot {
  @apply bg-red-500;
}
```

- [ ] **Step 4: `index.ts`**

```ts
export * from "./ConnectionPill";
```

- [ ] **Step 5: Run + commit**

```bash
cd frontend && npm run test -- src/components/ConnectionPill --coverage
git add frontend/src/components/ConnectionPill/
git commit -m "feat(frontend): add ConnectionPill backed by useConnectionStatus"
```
