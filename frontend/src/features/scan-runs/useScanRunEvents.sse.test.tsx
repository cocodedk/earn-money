import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { MockEventSource, installMockEventSource } from "../../test/sseMock";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeEvent } from "./__fixtures__/event";
import {
  RUN_A,
  RUN_B,
  lastInstance,
  waitConnected,
} from "./__fixtures__/sseTestHelpers";
import { useScanRunEvents } from "./useScanRunEvents";

let uninstall: () => void;
beforeEach(() => {
  uninstall = installMockEventSource();
  localStorage.removeItem("disable_live_events");
});
afterEach(() => {
  uninstall();
  localStorage.removeItem("disable_live_events");
});

describe("useScanRunEvents — SSE primary path", () => {
  it("opens EventSource against expected URL on mount", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    expect(lastInstance().url).toBe(`/sse/scan-runs/${RUN_A}/events/`);
  });

  it("appends emitted messages in order", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => lastInstance().emit(makeEvent({ id: "e1" })));
    act(() => lastInstance().emit(makeEvent({ id: "e2" })));
    await waitFor(() => expect(result.current.events.length).toBe(2));
    expect(result.current.events.map((e) => e.id)).toEqual(["e1", "e2"]);
  });

  it("duplicate id replaces existing entry in place", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => lastInstance().emit(makeEvent({ id: "e1", message: "first" })));
    act(() => lastInstance().emit(makeEvent({ id: "e2", message: "two" })));
    act(() => lastInstance().emit(makeEvent({ id: "e1", message: "replaced" })));
    await waitFor(() => expect(result.current.events.length).toBe(2));
    expect(result.current.events[0]).toMatchObject({ id: "e1", message: "replaced" });
    expect(result.current.events[1].id).toBe("e2");
  });

  it("evicts oldest when buffer exceeds maxBuffer", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true, maxBuffer: 2 }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => lastInstance().emit(makeEvent({ id: "e1" })));
    act(() => lastInstance().emit(makeEvent({ id: "e2" })));
    act(() => lastInstance().emit(makeEvent({ id: "e3" })));
    await waitFor(() => expect(result.current.events.length).toBe(2));
    expect(result.current.events.map((e) => e.id)).toEqual(["e2", "e3"]);
  });

  it("clear() empties buffer without closing connection", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => lastInstance().emit(makeEvent({ id: "e1" })));
    await waitFor(() => expect(result.current.events.length).toBe(1));
    act(() => result.current.clear());
    expect(result.current.events).toEqual([]);
    expect(result.current.status).toBe("connected");
    expect(lastInstance().readyState).toBe(1);
  });

  it("clear() does not issue any network call", async () => {
    const fetchSpy = vi.spyOn(global, "fetch");
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => result.current.clear());
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("reconnect() closes current and opens fresh instance", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    const first = lastInstance();
    act(() => result.current.reconnect());
    expect(first.readyState).toBe(2);
    expect(MockEventSource.instances.length).toBe(2);
    await waitConnected(result);
  });

  it("does not open instance when scanRunId is undefined", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(undefined, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await new Promise((r) => setTimeout(r, 10));
    expect(MockEventSource.instances.length).toBe(0);
    expect(result.current.status).toBe("closed");
  });

  it("does not open instance when livePolling is false", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useScanRunEvents(RUN_A, { livePolling: false }), {
      wrapper: Wrapper,
    });
    await new Promise((r) => setTimeout(r, 10));
    expect(MockEventSource.instances.length).toBe(0);
  });

  it("closes instance when livePolling flips true → false", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result, rerender } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunEvents(RUN_A, { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await waitConnected(result);
    const inst = lastInstance();
    rerender({ live: false });
    expect(inst.readyState).toBe(2);
    expect(result.current.status).toBe("closed");
  });

  it("opens fresh instance when livePolling flips false → true", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result, rerender } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunEvents(RUN_A, { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: false } },
    );
    expect(MockEventSource.instances.length).toBe(0);
    rerender({ live: true });
    await waitConnected(result);
    expect(MockEventSource.instances.length).toBe(1);
  });

  it("scanRunId A → B closes A, opens B, clears buffer", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useScanRunEvents(id, { livePolling: true }),
      { wrapper: Wrapper, initialProps: { id: RUN_A } },
    );
    await waitConnected(result);
    act(() => lastInstance().emit(makeEvent({ id: "e1" })));
    await waitFor(() => expect(result.current.events.length).toBe(1));
    const first = lastInstance();
    rerender({ id: RUN_B });
    expect(first.readyState).toBe(2);
    await waitConnected(result);
    expect(lastInstance().url).toBe(`/sse/scan-runs/${RUN_B}/events/`);
    expect(result.current.events).toEqual([]);
  });

  it("closes instance on unmount", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result, unmount } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    const inst = lastInstance();
    unmount();
    expect(inst.readyState).toBe(2);
  });
});
