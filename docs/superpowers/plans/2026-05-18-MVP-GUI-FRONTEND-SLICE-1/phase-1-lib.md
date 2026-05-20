# Phase 1 — Library code (types, http, parseApiError)

Builds the typed `fetch` wrapper and the error parser every page / hook will consume.

---

### Task E: API DTO types

**Files:**
- Create: `frontend/src/types/api.ts`

- [ ] **Step 1: Create the file**

`frontend/src/types/api.ts`:

```ts
// Mirrors docs/superpowers/specs/2026-05-18-MVP-GUI/11-api.md
export type Iso8601 = string;
export type Uuid = string;

export type ScanRunStatus =
  | "queued" | "running" | "paused" | "stopping" | "stopped" | "failed" | "done";

export type TargetStatus = "active" | "retired";

export type Severity = "info" | "low" | "medium" | "high" | "critical";

export type Project = {
  id: Uuid;
  name: string;
  description: string;
  target_count: number;
  scan_run_count: number;
  created_at: Iso8601;
};

export type CreateProjectBody = {
  name: string;
  description: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type HealthResponse = {
  status: "ok" | "degraded" | "down";
  db: boolean;
  redis?: boolean;
  worker?: boolean;
  version?: string;
};
```

Types are not exercised by tests directly — they're referenced by every other test file from Task F onwards, which covers them via use.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat(frontend): add API DTO types matching contract"
```

---

### Task F: `http` client + `parseApiError`

**Files:**
- Create: `frontend/src/lib/http.ts`
- Create: `frontend/src/lib/parseApiError.ts`
- Create: `frontend/src/lib/parseApiError.test.ts`
- Create: `frontend/src/lib/http.test.ts`

- [ ] **Step 1: Write `parseApiError.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { parseApiError } from "./parseApiError";

describe("parseApiError", () => {
  it("classifies field-keyed 400 as kind=field", async () => {
    const response = new Response(
      JSON.stringify({ name: ["already exists"] }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
    expect(await parseApiError(response)).toEqual({
      kind: "field",
      errors: { name: ["already exists"] },
    });
  });

  it("classifies non_field_errors 400 as kind=non_field", async () => {
    const response = new Response(
      JSON.stringify({ non_field_errors: ["bad combo"] }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
    expect(await parseApiError(response)).toEqual({
      kind: "non_field",
      errors: ["bad combo"],
    });
  });

  it("classifies non-validation 4xx as kind=detail", async () => {
    const response = new Response(JSON.stringify({ detail: "Not found." }), {
      status: 404,
      headers: { "content-type": "application/json" },
    });
    expect(await parseApiError(response)).toEqual({
      kind: "detail",
      detail: "Not found.",
      status: 404,
    });
  });

  it("classifies 5xx as kind=server", async () => {
    const response = new Response("Server boom", { status: 503 });
    expect(await parseApiError(response)).toEqual({
      kind: "server",
      status: 503,
    });
  });

  it("classifies thrown fetch errors as kind=network", async () => {
    expect(parseApiError(new TypeError("Failed to fetch"))).toEqual({
      kind: "network",
    });
  });
});
```

- [ ] **Step 2: Run test, see it fail**

```bash
cd frontend && npm run test -- src/lib/parseApiError.test.ts
```

Expected: FAIL "Cannot find module './parseApiError'".

- [ ] **Step 3: Implement `parseApiError.ts`**

```ts
export type ApiError =
  | { kind: "field"; errors: Record<string, string[]> }
  | { kind: "non_field"; errors: string[] }
  | { kind: "detail"; detail: string; status: number }
  | { kind: "server"; status: number }
  | { kind: "network" };

export async function parseApiError(
  input: Response | Error,
): Promise<ApiError> | ApiError {
  if (input instanceof Error) {
    return { kind: "network" };
  }
  if (input.status >= 500) {
    return { kind: "server", status: input.status };
  }
  const body = (await input.json().catch(() => ({}))) as Record<string, unknown>;
  if (input.status === 400) {
    if (Array.isArray(body.non_field_errors)) {
      return { kind: "non_field", errors: body.non_field_errors as string[] };
    }
    return { kind: "field", errors: body as Record<string, string[]> };
  }
  const detail = typeof body.detail === "string" ? body.detail : "Request failed";
  return { kind: "detail", detail, status: input.status };
}
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
cd frontend && npm run test -- src/lib/parseApiError.test.ts --coverage
```

Expected: 5 passed; 100% line / branch / function / statement on `parseApiError.ts`.

- [ ] **Step 5: Write `http.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { http as msw, HttpResponse } from "msw";
import { server } from "../test/server";
import { http } from "./http";

describe("http", () => {
  it("returns parsed JSON on 2xx", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    const data = await http<{ count: number }>("/api/projects/");
    expect(data.count).toBe(0);
  });

  it("throws on non-2xx with the raw Response attached", async () => {
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ detail: "Forbidden." }, { status: 403 }),
      ),
    );
    await expect(http("/api/projects/")).rejects.toMatchObject({
      response: expect.objectContaining({ status: 403 }),
    });
  });

  it("sends JSON body and content-type on POST", async () => {
    let receivedBody: unknown = null;
    server.use(
      msw.post("/api/projects/", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json({ id: "u1" }, { status: 201 });
      }),
    );
    const result = await http<{ id: string }>("/api/projects/", {
      method: "POST",
      body: { name: "X", description: "Y" },
    });
    expect(result.id).toBe("u1");
    expect(receivedBody).toEqual({ name: "X", description: "Y" });
  });
});
```

- [ ] **Step 6: Run, see fail**

```bash
cd frontend && npm run test -- src/lib/http.test.ts
```

Expected: FAIL "Cannot find module './http'".

- [ ] **Step 7: Implement `http.ts`**

```ts
type HttpOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
};

export class HttpError extends Error {
  constructor(public response: Response) {
    super(`HTTP ${response.status}`);
    this.name = "HttpError";
  }
}

export async function http<T>(url: string, options: HttpOptions = {}): Promise<T> {
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: options.body ? { "content-type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  };
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new HttpError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
```

- [ ] **Step 8: Run tests, verify coverage**

```bash
cd frontend && npm run test -- src/lib/http.test.ts --coverage
```

Expected: 3 passed; 100% coverage on `http.ts` (note the `204` branch is uncovered yet — add a fourth test).

- [ ] **Step 9: Add the 204 test**

Append to `frontend/src/lib/http.test.ts` inside the `describe`:

```ts
it("returns undefined on 204", async () => {
  server.use(
    msw.delete("/api/projects/u1/", () => new HttpResponse(null, { status: 204 })),
  );
  await expect(
    http("/api/projects/u1/", { method: "DELETE" }),
  ).resolves.toBeUndefined();
});
```

- [ ] **Step 10: Run again, confirm 100% coverage**

```bash
cd frontend && npm run test -- src/lib/ --coverage
```

Expected: all `src/lib/**` 100/100/100/100.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/lib/ frontend/src/test/
git commit -m "feat(frontend): add http client + parseApiError with full coverage"
```
