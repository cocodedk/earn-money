# Task 4 — mount panel on `TargetResult`

**Goal:** Render `TargetAuthEventsPanel` on the target result page, immediately between `TargetEvidencePanel` and `TargetEventsTable`. Verify DOM order with an integration test.

**Files:**
- Modify: `frontend/src/features/targets/TargetResult.tsx`
- Modify: `frontend/src/features/targets/TargetResult.test.tsx`

## Steps

- [ ] **Step 1: Write the failing integration test**

Open `frontend/src/features/targets/TargetResult.test.tsx` and append a new `it(...)` inside the existing top-level `describe`:

```tsx
  it("renders TargetAuthEventsPanel between Evidence and Events when there are auth events", async () => {
    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(TARGET)),
      msw.get("/api/scan-runs/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/findings/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/evidence/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/events/", ({ request }) => {
        const types = new URL(request.url).searchParams.getAll("type");
        if (types.length === 3) {
          return HttpResponse.json(
            paginatedJson([
              makeEvent({
                id: "auth-1",
                type: "auth.fixture_required",
                message: "fixture missing",
              }),
            ]),
          );
        }
        return HttpResponse.json(emptyPage());
      }),
    );
    mountTargetResult();
    const auth = await screen.findByTestId("target-auth-events-section");
    const events = await screen.findByTestId("target-events-section");
    const positions = [auth, events].map((el) =>
      Array.from(el.parentNode!.childNodes).indexOf(el),
    );
    expect(positions[0]).toBeLessThan(positions[1]);
  });
```

- [ ] **Step 2: Run the test, confirm it fails**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult.test.tsx
```
Expected: FAIL — `target-auth-events-section` not in the DOM.

- [ ] **Step 3: Render the panel in `TargetResult.tsx`**

Add the import and slot in `frontend/src/features/targets/TargetResult.tsx`:

```tsx
// add to imports near the other TargetResult/ siblings:
import { TargetAuthEventsPanel } from "./TargetResult/TargetAuthEventsPanel";

// inside DetailBody, between TargetEvidencePanel and TargetEventsTable:
      <TargetEvidencePanel targetId={target.id} />
      <TargetAuthEventsPanel targetId={target.id} />
      <TargetEventsTable targetId={target.id} />
```

- [ ] **Step 4: Run the test, confirm it passes**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult.test.tsx
```
Expected: all PASS, including the new integration test.

- [ ] **Step 5: Run the full targets-feature suite for regressions**

```bash
cd frontend && npx vitest run src/features/targets
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/targets/TargetResult.tsx \
        frontend/src/features/targets/TargetResult.test.tsx
git commit -m "feat(frontend): mount TargetAuthEventsPanel between Evidence and Events"
```
