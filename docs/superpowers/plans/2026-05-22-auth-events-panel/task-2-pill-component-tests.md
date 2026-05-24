# Task 2 (continued) — AuthEventPill variant + interaction + a11y tests

Continuation of [task-2-pill-component.md](task-2-pill-component.md). Run after Step 4 of the parent task passes. After Step 6 below, the parent task's Step 6 (commit) covers all three files together.

- [ ] **Step 5: Add variant + interaction + a11y tests**

Append to `AuthEventPill.test.tsx`:

```tsx
  it.each([
    ["auth.probe_refused", "warning"],
    ["auth.fixture_required", "info"],
    ["auth.finding_candidate", "alert"],
  ])("event type %s renders variant %s", (type, variant) => {
    const { container } = render(
      <AuthEventPill event={makeEvent({ type })} />,
    );
    expect(container.querySelector(`[data-variant="${variant}"]`)).not.toBeNull();
  });

  it("click toggles expanded and reveals message + payload", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const ue = userEvent.setup();
    render(
      <AuthEventPill
        event={makeEvent({
          type: "auth.fixture_required",
          message: "needs juiceshop creds",
          data: { fixture: "juiceshop-admin" },
        })}
      />,
    );
    const btn = screen.getByRole("button");
    expect(screen.queryByTestId("auth-event-pill-detail")).toBeNull();
    await ue.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("needs juiceshop creds")).toBeInTheDocument();
    expect(screen.getByTestId("auth-event-pill-detail")).toHaveTextContent(
      /"fixture": "juiceshop-admin"/,
    );
    await ue.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "false");
  });

  it("renders an empty JSON object when event.data is empty", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const ue = userEvent.setup();
    render(
      <AuthEventPill
        event={makeEvent({
          type: "auth.fixture_required",
          data: {},
        })}
      />,
    );
    await ue.click(screen.getByRole("button"));
    expect(screen.getByTestId("auth-event-pill-detail")).toHaveTextContent("{}");
  });

  it("Enter and Space both toggle expand", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const ue = userEvent.setup();
    render(<AuthEventPill event={makeEvent({ type: "auth.probe_refused" })} />);
    const btn = screen.getByRole("button");
    btn.focus();
    await ue.keyboard("{Enter}");
    expect(btn).toHaveAttribute("aria-expanded", "true");
    await ue.keyboard(" ");
    expect(btn).toHaveAttribute("aria-expanded", "false");
  });

  it("falls back to raw type and info variant for an unknown event type", () => {
    const { container } = render(
      <AuthEventPill event={makeEvent({ type: "auth.unknown" })} />,
    );
    expect(screen.getByText("auth.unknown")).toBeInTheDocument();
    expect(container.querySelector('[data-variant="info"]')).not.toBeNull();
  });
```

- [ ] **Step 6: Run tests with coverage**

```bash
cd frontend && npx vitest run src/features/targets/TargetResult/AuthEventPill.test.tsx --coverage
```
Expected: all PASS; `AuthEventPill.tsx` line coverage at 100%, with branch coverage for known variants, unknown fallback, and collapsed/expanded rendering.
