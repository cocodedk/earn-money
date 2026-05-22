import { describe, it, expect } from "vitest";
import { http as msw, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { TargetAuthEventsPanel } from "./TargetAuthEventsPanel";
import { makeEvent } from "../../scan-runs/__fixtures__/event";

const TARGET_ID = "22222222-2222-2222-2222-222222222222";

function authPage(
  rows: ReturnType<typeof makeEvent>[],
  next: string | null = null,
) {
  // backend returns oldest-first; the hook reverses for the component,
  // so feed tests the same oldest-first ordering the API returns.
  return { count: rows.length, next, previous: null, results: rows };
}

describe("TargetAuthEventsPanel", () => {
  it("renders nothing when count is 0", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/events/", () => {
        calls += 1;
        return HttpResponse.json(authPage([]));
      }),
    );
    const { container } = renderWithProviders(
      <TargetAuthEventsPanel targetId={TARGET_ID} />,
    );
    await waitFor(() => expect(calls).toBe(1));
    expect(container.firstChild).toBeNull();
  });

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
});
