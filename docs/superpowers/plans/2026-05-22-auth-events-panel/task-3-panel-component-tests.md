# Task 3 (continued) — TargetAuthEventsPanel populated + edge tests

Continuation of [task-3-panel-component.md](task-3-panel-component.md). Run after Step 4 of the parent task passes. After Step 6 below, the parent task's Step 6 (commit) covers all three files together.

- [ ] **Step 5: Add populated + ordering + truncation + error tests**

Append to `TargetAuthEventsPanel.test.tsx`:

```tsx
  it("renders one pill per event, newest first (hook reversed)", async () => {
    server.use(
      msw.get("/api/events/", () =>
        HttpResponse.json(
          authPage([
            makeEvent({
              id: "old",
              type: "auth.probe_refused",
              created_at: "2026-05-22T08:00:00Z",
            }),
            makeEvent({
              id: "new",
              type: "auth.finding_candidate",
              created_at: "2026-05-22T10:00:00Z",
            }),
          ]),
        ),
      ),
    );
    renderWithProviders(<TargetAuthEventsPanel targetId={TARGET_ID} />);
    const buttons = await screen.findAllByRole("button");
    expect(buttons).toHaveLength(2);
    expect(buttons[0]).toHaveTextContent("Finding candidate");
    expect(buttons[1]).toHaveTextContent("Probe refused");
    expect(
      screen.getByRole("heading", { name: /Auth events for target \(2\)/ }),
    ).toBeInTheDocument();
  });

  it("shows +N more footer when next is non-null and remaining > 0", async () => {
    const rows = Array.from({ length: 50 }, (_, i) =>
      makeEvent({
        id: `e${i}`,
        type: "auth.probe_refused",
        created_at: `2026-05-22T0${i % 10}:00:00Z`,
      }),
    );
    server.use(
      msw.get("/api/events/", () =>
        HttpResponse.json({
          count: 73,
          next: "/api/events/?page=2",
          previous: null,
          results: rows,
        }),
      ),
    );
    renderWithProviders(<TargetAuthEventsPanel targetId={TARGET_ID} />);
    const more = await screen.findByTestId("target-auth-events-more");
    expect(more).toHaveTextContent("+23 more in the full events feed below.");
  });

  it("hides +N footer when next is null", async () => {
    server.use(
      msw.get("/api/events/", () =>
        HttpResponse.json(
          authPage([makeEvent({ type: "auth.probe_refused" })], null),
        ),
      ),
    );
    renderWithProviders(<TargetAuthEventsPanel targetId={TARGET_ID} />);
    await screen.findByRole("button");
    expect(screen.queryByTestId("target-auth-events-more")).toBeNull();
  });

  it("renders nothing if the auth-events request fails", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/events/", () => {
        calls += 1;
        return HttpResponse.json({ detail: "boom" }, { status: 500 });
      }),
    );
    const { container } = renderWithProviders(
      <TargetAuthEventsPanel targetId={TARGET_ID} />,
    );
    await waitFor(() => expect(calls).toBe(1));
    expect(container.firstChild).toBeNull();
  });
```

- [ ] **Step 6: Run all panel tests with coverage**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx --coverage
```
Expected: 5/5 PASS; `TargetAuthEventsPanel.tsx` line coverage at 100%, with branch coverage for empty, populated, paginated, non-paginated, and request-error paths.
