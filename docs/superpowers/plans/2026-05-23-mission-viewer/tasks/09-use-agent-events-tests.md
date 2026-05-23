# Task 9 — Tests: useAgentEvents

Test code for [Task 9](09-use-agent-events.md).

Create `frontend/src/features/missions/useAgentEvents.test.tsx`:

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { MockEventSource } from "../../test/sseMock";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { useAgentEvents } from "./useAgentEvents";
import { SESSION_ID, SCAN_RUN_ID } from "./__fixtures__/mission";
import { makeEvent } from "../scan-runs/__fixtures__/event";

function agentEvent(type: string, extra: Record<string, unknown> = {}) {
  return makeEvent({
    id: `evt-${Math.random().toString(36).slice(2, 8)}`,
    type,
    data: { session_id: SESSION_ID, ...extra },
  });
}

describe("useAgentEvents", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    MockEventSource.autoOpen = true;
  });
  afterEach(() => {
    MockEventSource.instances = [];
    MockEventSource.autoOpen = true;
  });

  it("filters agent events matching the session id", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];
    act(() => es.emit(agentEvent("agent.action_executed")));
    act(() => es.emit(makeEvent({ type: "target_started" })));
    expect(result.current.processedCount).toBe(1);
  });

  it("ignores agent events for a different session", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];
    act(() =>
      es.emit(makeEvent({
        type: "agent.action_executed",
        data: { session_id: "other-session" },
      })),
    );
    expect(result.current.processedCount).toBe(0);
  });

  it("does not re-process duplicate event IDs", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];
    const evt = agentEvent("agent.action_executed");
    act(() => es.emit(evt));
    act(() => es.emit(evt));
    expect(result.current.processedCount).toBe(1);
  });

  it("updates budget overlay from budget_snapshot", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];
    act(() =>
      es.emit(agentEvent("agent.action_executed", {
        budget_snapshot: { turns: 5, mission: { turns: 5 } },
      })),
    );
    expect(result.current.budgetOverlay?.mission?.turns).toBe(5);
  });

  it("returns null overlay when sessionId is undefined", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(undefined, undefined, false),
      { wrapper: Wrapper },
    );
    expect(result.current.budgetOverlay).toBeNull();
  });

  it("does not open SSE when isTerminal is true", () => {
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, true),
      { wrapper: Wrapper },
    );
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("ignores non-agent events", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];
    act(() => es.emit(makeEvent({ type: "scan.started" })));
    act(() => es.emit(makeEvent({ type: "target.updated" })));
    expect(result.current.processedCount).toBe(0);
  });

  it("processes turn lifecycle events for the matching session", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];
    act(() => es.emit(agentEvent("agent.turn_started")));
    act(() => es.emit(agentEvent("agent.turn_completed")));
    expect(result.current.processedCount).toBe(2);
  });
});
```
