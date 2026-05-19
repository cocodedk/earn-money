# Phase 0 — Findings + Evidence API clients

Hooks for the global list endpoints with filter querystrings.

---

### Task A: `Findings` API client

**Files:**
- Create: `frontend/src/features/findings/api.ts`
- Create: `frontend/src/features/findings/api.test.tsx`

Filters per `08-findings.md`: `project, target, scan_run, stub, severity, confidence, status`. Hook accepts a partial filter object; only set keys go into the querystring.

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useFindingsQuery, useFindingDetailQuery, FINDINGS_KEY } from "./api";

describe("useFindingsQuery", () => {
  it("fetches unfiltered global list", async () => {
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.count).toBe(0));
  });

  it.each([
    ["project", "p1"],
    ["target", "t1"],
    ["scan_run", "r1"],
    ["stub", "1.1"],
    ["severity", "high"],
    ["confidence", "medium"],
    ["status", "candidate"],
  ] as const)("includes ?%s=%s in the querystring when set", async (key, value) => {
    let url: URL | null = null;
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useFindingsQuery({ [key]: value } as Record<string, string>), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(url).not.toBeNull());
    expect(url!.searchParams.get(key)).toBe(value);
  });
});

describe("useFindingDetailQuery", () => {
  it("fetches by id", async () => {
    server.use(
      msw.get("/api/findings/f1/", () =>
        HttpResponse.json({
          id: "f1",
          scan_run: "r1",
          target: "t1",
          stub_slug: "1.1",
          title: "Express detected",
          category: "framework-detection",
          severity: "info",
          confidence: "high",
          status: "candidate",
          data: { technology: "Express" },
          created_at: "2026-05-18T20:00:00.000000Z",
          updated_at: "2026-05-18T20:00:00.000000Z",
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingDetailQuery("f1"), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.data?.title).toBe("Express detected"));
  });

  it("stays disabled when id is null", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useFindingDetailQuery(null), {
      wrapper: Wrapper,
    });
    expect(result.current.isFetching).toBe(false);
  });
});
```

- [ ] **Step 2: Implement `api.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type {
  Confidence,
  Finding,
  FindingStatus,
  Paginated,
  Severity,
  Uuid,
} from "../../types/api";

export const FINDINGS_KEY = ["findings"] as const;

export type FindingsFilter = {
  project?: Uuid;
  target?: Uuid;
  scan_run?: Uuid;
  stub?: string;
  severity?: Severity;
  confidence?: Confidence;
  status?: FindingStatus;
};

function buildQuery(filter: FindingsFilter): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filter)) {
    if (v !== undefined && v !== "") params.set(k, v as string);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useFindingsQuery(filter: FindingsFilter = {}) {
  return useQuery({
    queryKey: [...FINDINGS_KEY, filter] as const,
    queryFn: () =>
      http<Paginated<Finding>>(`/api/findings/${buildQuery(filter)}`),
  });
}

export function useFindingDetailQuery(id: Uuid | null) {
  return useQuery({
    queryKey: [...FINDINGS_KEY, id] as const,
    queryFn: () => http<Finding>(`/api/findings/${id!}/`),
    enabled: Boolean(id),
  });
}
```

- [ ] **Step 3: Run + commit + /simplify**

```bash
npm run test -- src/features/findings/api
git add frontend/src/features/findings/api.{ts,test.tsx}
git commit -m "feat(frontend): add Findings API client with filters + detail"
```

---

### Task B: `Evidence` API client

Mirrors Task A. Filters per `09-evidence.md`: `project, target, scan_run, finding, source`.

**Files:**
- Create: `frontend/src/features/evidence/api.ts`
- Create: `frontend/src/features/evidence/api.test.tsx`

- [ ] **Step 1: Test** — same shape as Findings tests, with the 5 evidence filters.

- [ ] **Step 2: Implement** `useEvidenceQuery(filter)` + `useEvidenceDetailQuery(id)`. Same `buildQuery` helper pattern (factor into shared `lib/buildQuery.ts` if it grows beyond two callers).

- [ ] **Step 3: Run + commit + /simplify**
