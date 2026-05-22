import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthEventPill } from "./AuthEventPill";
import { makeEvent } from "../../scan-runs/__fixtures__/event";

describe("AuthEventPill", () => {
  it("collapsed shows type label and timestamp", () => {
    render(
      <AuthEventPill
        event={makeEvent({
          type: "auth.probe_refused",
          created_at: "2026-05-22T10:15:00Z",
        })}
      />,
    );
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Probe refused")).toBeInTheDocument();
    expect(screen.getByTestId("auth-event-pill-time")).toHaveTextContent(/\d{1,2}:\d{2}/);
  });

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
});
