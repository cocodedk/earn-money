# Task 1 — query hook: URL + reverse

**Goal:** `useTargetAuthEventsQuery(targetId)` issues a single request to `/api/events/` with `target=<id>` plus three `?type=` params, then reverses the backend's oldest-first `results` to newest-first.

**Files:**
- Create: `frontend/src/features/targets/api.auth-events.ts`
- Test: `frontend/src/features/targets/api.auth-events.test.tsx`

## Steps

- [ ] **Step 1: Write the failing URL test**

```tsx
// api.auth-events.test.tsx
import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useTargetAuthEventsQuery } from "./api.auth-events";
import { makeEvent } from "../scan-runs/__fixtures__/event";

const TARGET_ID = "22222222-2222-2222-2222-222222222222";

describe("useTargetAuthEventsQuery", () => {
  it("requests /api/events/ with target + three ?type= params", async () => {
    let calls = 0;
    let target = "";
    let types: string[] = [];
    server.use(
      msw.get("/api/events/", ({ request }) => {
        calls += 1;
        const url = new URL(request.url);
        target = url.searchParams.get("target") ?? "";
        types = url.searchParams.getAll("type");
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetAuthEventsQuery(TARGET_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
    expect(target).toBe(TARGET_ID);
    expect(types).toEqual([
      "auth.probe_refused",
      "auth.fixture_required",
      "auth.finding_candidate",
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/features/targets/api.auth-events.test.tsx
```
Expected: FAIL — module `./api.auth-events` not found.

- [ ] **Step 3: Write the minimal hook**

```ts
// api.auth-events.ts
import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Event, Paginated } from "../../types/api";
import { TARGETS_KEY } from "./api";

export const AUTH_EVENT_TYPES = [
  "auth.probe_refused",
  "auth.fixture_required",
  "auth.finding_candidate",
] as const;

export function useTargetAuthEventsQuery(targetId: string | undefined) {
  const id = targetId ?? "";
  return useQuery({
    queryKey: [...TARGETS_KEY, id, "auth-events"] as const,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("target", id);
      for (const t of AUTH_EVENT_TYPES) params.append("type", t);
      const page = await http<Paginated<Event>>(
        `/api/events/?${params.toString()}`,
      );
      return { ...page, results: [...page.results].reverse() };
    },
    enabled: Boolean(targetId),
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/features/targets/api.auth-events.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Add reverse-order test + disabled test**

Append to `api.auth-events.test.tsx`:

```tsx
  it("reverses backend oldest-first results to newest-first", async () => {
    server.use(
      msw.get("/api/events/", () =>
        HttpResponse.json({
          count: 3,
          next: null,
          previous: null,
          results: [
            makeEvent({ id: "old", created_at: "2026-05-22T08:00:00Z" }),
            makeEvent({ id: "mid", created_at: "2026-05-22T09:00:00Z" }),
            makeEvent({ id: "new", created_at: "2026-05-22T10:00:00Z" }),
          ],
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTargetAuthEventsQuery(TARGET_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.count).toBe(3));
    expect(result.current.data?.results.map((e) => e.id)).toEqual([
      "new",
      "mid",
      "old",
    ]);
  });

  it("is disabled when targetId is undefined", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/events/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useTargetAuthEventsQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });
```

- [ ] **Step 6: Run all hook tests**

```bash
cd frontend && npx vitest run src/features/targets/api.auth-events.test.tsx
```
Expected: 3/3 PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/targets/api.auth-events.ts \
        frontend/src/features/targets/api.auth-events.test.tsx
git commit -m "feat(frontend): useTargetAuthEventsQuery — multi-?type= + client reverse"
```
