# Task 5 — e2e smoke

**Goal:** End-to-end test driving from `/targets/:id/results` through the auth panel — visible pill, click expands, message + payload appear.

**Files:**
- Modify: `frontend/src/App.e2e.target-result.test.tsx`

## Steps

- [ ] **Step 1: Add a new e2e test**

At the end of the existing top-level `describe("end-to-end · target result", …)` block:

```tsx
  it("auth events panel appears for a target with auth events and is expandable", async () => {
    const target = TARGET;
    server.use(
      msw.get("/api/projects/", () => HttpResponse.json(paged([PROJECT]))),
      msw.get("/api/targets/", () => HttpResponse.json(paged([target]))),
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(target)),
      msw.get("/api/scan-runs/", () => HttpResponse.json(paged([]))),
      msw.get("/api/findings/", () => HttpResponse.json(paged([]))),
      msw.get("/api/evidence/", () => HttpResponse.json(paged([]))),
      msw.get("/api/events/", ({ request }) => {
        const types = new URL(request.url).searchParams.getAll("type");
        if (types.length === 3) {
          return HttpResponse.json(
            paged([
              makeEvent({
                id: "ev-auth-1",
                type: "auth.fixture_required",
                message: "needs lab creds",
                data: { fixture: "dvwa-admin" },
              }),
            ]),
          );
        }
        return HttpResponse.json(paged([]));
      }),
    );
    renderWithProviders(<App />, { route: `/targets/${TARGET_ID}/results` });
    const pillBtn = await screen.findByRole("button", { name: /Fixture required/ });
    await userEvent.click(pillBtn);
    expect(screen.getByText("needs lab creds")).toBeInTheDocument();
    expect(
      screen.getByTestId("auth-event-pill-detail"),
    ).toHaveTextContent(/"fixture": "dvwa-admin"/);
  });
```

If `PROJECT` is not yet declared at the top of this file, add it near `TARGET` with the same shape used in `frontend/src/features/targets/TargetResult/__fixtures__/testkit.tsx`.

- [ ] **Step 2: Run the e2e**

```bash
cd frontend && npx vitest run src/App.e2e.target-result.test.tsx
```
Expected: all PASS.

- [ ] **Step 3: Full frontend test suite + tsc**

```bash
cd frontend && npm run test && npx tsc -b
```
Expected: green across the board, no tsc errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.e2e.target-result.test.tsx
git commit -m "test(frontend): e2e — auth events panel renders + expands on target page"
```
