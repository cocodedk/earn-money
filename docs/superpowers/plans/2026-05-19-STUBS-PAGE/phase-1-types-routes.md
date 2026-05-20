# Phase 1 — Types + routes

Add the `StubStatus`, `StubSummary`, `Stub` types alongside existing `Target` types and register the `/stubs/:slug` route.

---

### Task A: Types + routes

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/app/routes.ts`

- [ ] **Step 1: Append to `frontend/src/types/api.ts`**

```ts
export type StubStatus = "pending" | "in-progress" | "blocked" | "done";

export type StubSummary = {
  slug: string;
  phase: number;
  spec: number;
  phase_slug: string;
  spec_slug: string;
  title: string;
  phase_title: string;
  category: string;
  status: StubStatus;
  fixture: string;
  path: string;
};

export type Stub = StubSummary & { body: string };
```

Peer-confirmed `StubStatus` is closed at the four values; today only `pending` and `done` are emitted across all 278 specs, but the type closes the union for compile-time safety.

- [ ] **Step 2: Edit `frontend/src/app/routes.ts`**

```ts
export const ROUTES = {
  index: "/",
  projects: "/projects",
  projectsNew: "/projects/new",
  targets: "/targets",
  targetsNew: "/targets/new",
  stubs: "/stubs",
  stubDetail: "/stubs/:slug",
  scanRuns: "/scan-runs",
  findings: "/findings",
  evidence: "/evidence",
  settings: "/settings",
} as const;
```

Helper for constructing the detail path at call sites — also added to the same file to keep routes co-located:

```ts
export const stubDetailPath = (slug: string) => `/stubs/${slug}`;
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: green. No tests are added at this phase — type / route additions are exercised by phases 2-5.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/app/routes.ts
git commit -m "feat(frontend): add Stub types + /stubs/:slug route"
```
