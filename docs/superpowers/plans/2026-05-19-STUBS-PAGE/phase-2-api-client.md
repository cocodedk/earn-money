# Phase 2 — API client + shared bare-array test helper

Two hooks (`useStubsQuery`, `useStubQuery`) over the bare-array `/api/stubs/` endpoint. Adds a `withBareArray` test helper next to the existing `withPaginated` so the stubs tests don't roll their own MSW handler.

---

### Task B: API client + hooks + helper

**Files:**
- Create: `frontend/src/features/stubs/api.ts`
- Create: `frontend/src/features/stubs/api.test.tsx`
- Modify: `frontend/src/test/helpers.tsx`

- [ ] **Step 1: Add `withBareArray` to `frontend/src/test/helpers.tsx`**

```ts
// Install a GET handler for an endpoint that returns a bare JSON array
// (used by /api/stubs/ — DRF pagination is intentionally disabled there).
export function withBareArray(path: string, rows: unknown[]) {
  server.use(msw.get(path, () => HttpResponse.json(rows)));
}
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/features/stubs/api.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { withBareArray } from "../../test/helpers";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { STUBS_KEY, useStubQuery, useStubsQuery } from "./api";

const STUB_SUMMARY = {
  slug: "1.1",
  phase: 1,
  spec: 1,
  phase_slug: "01-information-gathering",
  spec_slug: "framework-detection",
  title: "Framework detection",
  phase_title: "Information gathering",
  category: "Content discovery",
  status: "done",
  fixture: "juice-shop",
  path: "01-information-gathering/01-framework-detection.md",
};

describe("useStubsQuery", () => {
  it("fetches a bare array and returns the list", async () => {
    withBareArray("/api/stubs/", [STUB_SUMMARY]);
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.length).toBe(1));
    expect(result.current.data?.[0].title).toBe("Framework detection");
  });
});

describe("useStubQuery", () => {
  it("fetches one stub including the markdown body", async () => {
    server.use(
      msw.get("/api/stubs/1.1/", () =>
        HttpResponse.json({ ...STUB_SUMMARY, body: "# 1.1\n\nbody text" }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubQuery("1.1"), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.body).toContain("body text"));
  });

  it("is disabled when slug is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/stubs/:slug/", () => {
        calls += 1;
        return HttpResponse.json(STUB_SUMMARY);
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useStubQuery(undefined), {
      wrapper: Wrapper,
    });
    // No data, no fetch.
    expect(result.current.isLoading).toBe(false);
    expect(calls).toBe(0);
  });

  it("exposes STUBS_KEY at the module level for cache lookups", () => {
    expect(STUBS_KEY).toEqual(["stubs"]);
  });
});
```

- [ ] **Step 3: Run the test — it must fail**

```bash
cd frontend && npm test -- src/features/stubs/api
```

Expected: module-not-found.

- [ ] **Step 4: Implement `api.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Stub, StubSummary } from "../../types/api";

export const STUBS_KEY = ["stubs"] as const;
export const stubKey = (slug: string) => [...STUBS_KEY, slug] as const;

export function useStubsQuery() {
  return useQuery({
    queryKey: STUBS_KEY,
    queryFn: () => http<StubSummary[]>("/api/stubs/"),
  });
}

export function useStubQuery(slug: string | undefined) {
  return useQuery({
    queryKey: stubKey(slug ?? ""),
    queryFn: () => http<Stub>(`/api/stubs/${slug}/`),
    enabled: Boolean(slug),
  });
}
```

- [ ] **Step 5: Re-run; verify pass + coverage 100%**

```bash
cd frontend && npm test -- src/features/stubs/api --coverage
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/stubs/api.ts frontend/src/features/stubs/api.test.tsx frontend/src/test/helpers.tsx
git commit -m "feat(frontend): add Stubs API client + bare-array test helper"
```
