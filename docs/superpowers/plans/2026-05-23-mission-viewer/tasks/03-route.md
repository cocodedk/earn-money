---
tier: FAST
depends_on: []
files:
  creates: []
  modifies: [frontend/src/app/routes.ts, frontend/src/app/routes.test.ts]
allow_extra_files: false
---

# Task 3: Route Registration

**Goal:** Add the `/missions/:sessionId` route and `missionDetailPath` helper.

**Files:**
- Modify: `frontend/src/app/routes.ts`
- Modify: `frontend/src/app/routes.test.ts`

- [ ] **Step 1: Write the failing route test**

Add to `frontend/src/app/routes.test.ts`:

```typescript
import {
  ROUTES,
  scanRunDetailPath,
  stubDetailPath,
  missionDetailPath,
} from "./routes";

// Add inside the existing describe block:

it("locks the mission detail route path", () => {
  expect(ROUTES.missionDetail).toBe("/missions/:sessionId");
});

it("builds a mission detail path from a session UUID", () => {
  expect(missionDetailPath("s-1")).toBe("/missions/s-1");
  expect(missionDetailPath("abc-123")).toBe("/missions/abc-123");
});

it("path-encodes the session id segment", () => {
  expect(missionDetailPath("abc/123")).toBe("/missions/abc%2F123");
  expect(missionDetailPath("id with spaces")).toBe("/missions/id%20with%20spaces");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/app/routes.test.ts`
Expected: FAIL — `missionDetailPath` not exported, `ROUTES.missionDetail` undefined.

- [ ] **Step 3: Add route and helper**

Add to `frontend/src/app/routes.ts`:

```typescript
// Add to ROUTES object, before the closing `} as const`:
  missionDetail: "/missions/:sessionId",

// Add at end of file:
export const missionDetailPath = (sessionId: string) =>
  `/missions/${encodeURIComponent(sessionId)}`;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/app/routes.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/routes.ts frontend/src/app/routes.test.ts
git commit -m "feat(frontend): add /missions/:sessionId route and helper"
```
