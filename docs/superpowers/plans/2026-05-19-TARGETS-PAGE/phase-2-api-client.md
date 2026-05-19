# Phase 2 — Targets API client

Mirror of `features/projects/api.ts`. Two hooks (`useTargetsQuery`, `useCreateTargetMutation`) and a shared `TARGETS_KEY`. Cache invalidation on successful create.

---

### Task B: API client + hooks

**Files:**
- Create: `frontend/src/features/targets/api.ts`
- Create: `frontend/src/features/targets/api.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/targets/api.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../../test/server";
import { TARGETS_KEY, useCreateTargetMutation, useTargetsQuery } from "./api";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return { client, Wrapper };
}

describe("useTargetsQuery", () => {
  it("fetches and returns the page of targets", async () => {
    server.use(
      msw.get("/api/targets/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "t-1",
              project: "p-1",
              base_url: "https://dvwa.cocode.dk",
              host: "dvwa.cocode.dk",
              ip: null,
              status: "active",
              created_at: "2026-05-19T08:00:00.000000Z",
              updated_at: "2026-05-19T08:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useTargetsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(result.current.data?.results[0].host).toBe("dvwa.cocode.dk");
  });
});

describe("useCreateTargetMutation", () => {
  it("POSTs the body and invalidates the targets list", async () => {
    let received: unknown = null;
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(
          {
            id: "t-new",
            project: "p-1",
            base_url: "https://dvwa.cocode.dk",
            host: "dvwa.cocode.dk",
            ip: null,
            status: "active",
            created_at: "2026-05-19T08:00:00.000000Z",
            updated_at: "2026-05-19T08:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    const { client, Wrapper } = makeWrapper();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateTargetMutation(), {
      wrapper: Wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync({
        project: "p-1",
        base_url: "https://dvwa.cocode.dk",
      });
    });
    expect(received).toEqual({
      project: "p-1",
      base_url: "https://dvwa.cocode.dk",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: TARGETS_KEY });
  });
});
```

- [ ] **Step 2: Run the test — it must fail**

```bash
cd frontend && npm run test -- src/features/targets/api
```

Expected: module-not-found error pointing at `./api`.

- [ ] **Step 3: Implement `api.ts`**

Create `frontend/src/features/targets/api.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { CreateTargetBody, Paginated, Target } from "../../types/api";

export const TARGETS_KEY = ["targets"] as const;

export function useTargetsQuery() {
  return useQuery({
    queryKey: TARGETS_KEY,
    queryFn: () => http<Paginated<Target>>("/api/targets/"),
  });
}

export function useCreateTargetMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTargetBody) =>
      http<Target>("/api/targets/", { method: "POST", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: TARGETS_KEY });
    },
  });
}
```

- [ ] **Step 4: Run the test — it must pass**

```bash
cd frontend && npm run test -- src/features/targets/api --coverage
```

Expected: all 2 tests pass; coverage report shows 100% on `api.ts`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/targets/api.ts frontend/src/features/targets/api.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add Targets API client with cache invalidation

useTargetsQuery + useCreateTargetMutation mirror the Projects API hooks.
Successful create invalidates the TARGETS_KEY so the list page refetches.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Run `/simplify` and iterate**

```bash
/simplify
```

Iterate fix → commit → `/simplify` until clean.

- [ ] **Step 7: Notify peer**

Send a chat-mcp ping (via `mcp__claude-chat__chat_message_agent`) to `agent-em-backend`:

> "Targets API client (phase 2) green. Two hooks shipped; cache invalidation tested. Moving to TargetsList (phase 3)."

This is the per-milestone peer check-in the operator asked for.
