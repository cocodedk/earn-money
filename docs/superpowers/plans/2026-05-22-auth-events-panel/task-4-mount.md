# Task 4 — mount panel on `TargetResult`

**Goal:** Render `TargetAuthEventsPanel` on the target result page, immediately between `TargetEvidencePanel` and `TargetEventsTable`. Verify DOM order with an integration test.

**Files:**
- Modify: `frontend/src/features/targets/TargetResult.tsx`
- Modify: `frontend/src/features/targets/TargetResult.test.tsx`
- Modify if missing selectors: `frontend/src/features/targets/TargetResult/TargetEvidencePanel.tsx`
- Modify if missing selectors: `frontend/src/features/targets/TargetResult/TargetEventsTable.tsx`

## Steps

- [ ] **Step 1: Write the failing integration test**

Open `frontend/src/features/targets/TargetResult.test.tsx` and append a new `it(...)` inside the existing top-level `describe`. Use this as a variation of the file's existing happy-path target-result test: keep the handlers that make Evidence and Events render, and override `/api/events/` so the auth-query branch returns one auth row while the full events feed branch returns empty. If `makeEvent` is not already imported, import it from `../scan-runs/__fixtures__/event`.

```tsx
  it("renders TargetAuthEventsPanel between Evidence and Events when there are auth events", async () => {
    const authEventsPage = (rows: ReturnType<typeof makeEvent>[]) => ({
      count: rows.length,
      next: null,
      previous: null,
      results: rows,
    });

    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(TARGET)),
      msw.get("/api/scan-runs/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/findings/", () => HttpResponse.json(emptyPage())),
      // If TargetEvidencePanel is conditional, copy the existing happy-path
      // evidence stub from this test file here so the evidence section renders.
      msw.get("/api/evidence/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/events/", ({ request }) => {
        const types = new URL(request.url).searchParams.getAll("type");
        if (types.length === 3) {
          return HttpResponse.json(
            authEventsPage([
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
    const evidence = await screen.findByTestId("target-evidence-section");
    const auth = await screen.findByTestId("target-auth-events-section");
    const events = await screen.findByTestId("target-events-section");
    expect(evidence.parentElement).toBe(auth.parentElement);
    expect(auth.parentElement).toBe(events.parentElement);
    const siblings = Array.from(auth.parentElement!.children);
    expect(siblings.indexOf(evidence)).toBeLessThan(siblings.indexOf(auth));
    expect(siblings.indexOf(auth)).toBeLessThan(siblings.indexOf(events));
  });
```

- [ ] **Step 2: Run the test, confirm it fails**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult.test.tsx
```
Expected: FAIL — normally `target-auth-events-section` is not in the DOM. If the failure is a missing `target-evidence-section` or `target-events-section` selector, handle that in Step 3 together with the mount change.

- [ ] **Step 3: Render the panel in `TargetResult.tsx` and ensure selectors**

Add the import and slot in `frontend/src/features/targets/TargetResult.tsx`:

```tsx
// add to imports near the other TargetResult/ siblings:
import { TargetAuthEventsPanel } from "./TargetResult/TargetAuthEventsPanel";

// inside DetailBody, between TargetEvidencePanel and TargetEventsTable:
      <TargetEvidencePanel targetId={target.id} />
      <TargetAuthEventsPanel targetId={target.id} />
      <TargetEventsTable targetId={target.id} />
```

Selector requirement for this integration test:

- `TargetEvidencePanel` outer section has `data-testid="target-evidence-section"`.
- `TargetAuthEventsPanel` outer section already has `data-testid="target-auth-events-section"` from Task 3.
- `TargetEventsTable` outer section has `data-testid="target-events-section"`.
- If either existing outer section lacks the selector, add only that `data-testid`; do not introduce wrappers or style changes.

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

If Step 3 added missing selector-only changes, use this command instead so the selector files are included in the same commit:

```bash
git add frontend/src/features/targets/TargetResult.tsx \
        frontend/src/features/targets/TargetResult.test.tsx \
        frontend/src/features/targets/TargetResult/TargetEvidencePanel.tsx \
        frontend/src/features/targets/TargetResult/TargetEventsTable.tsx
git commit -m "feat(frontend): mount TargetAuthEventsPanel between Evidence and Events"
```
