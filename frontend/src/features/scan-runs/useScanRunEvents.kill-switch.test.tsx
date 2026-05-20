import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { MockEventSource, installMockEventSource } from "../../test/sseMock";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import {
  RUN_A,
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

describe("useScanRunEvents — malformed frames and kill switch", () => {
  it("silently drops malformed (unparseable) SSE frame", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => {
      lastInstance().onmessage?.(
        new MessageEvent("message", { data: "{not-json" }),
      );
    });
    expect(result.current.events).toEqual([]);
    expect(result.current.status).toBe("connected");
  });

  it("drops null payload (JSON.parse('null'))", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => {
      lastInstance().onmessage?.(
        new MessageEvent("message", { data: "null" }),
      );
    });
    expect(result.current.events).toEqual([]);
    expect(result.current.status).toBe("connected");
  });

  it("drops valid JSON missing id", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => {
      lastInstance().onmessage?.(
        new MessageEvent("message", { data: '{"type":"x"}' }),
      );
    });
    expect(result.current.events).toEqual([]);
    expect(result.current.status).toBe("connected");
  });

  it("drops valid JSON missing type", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    act(() => {
      lastInstance().onmessage?.(
        new MessageEvent("message", { data: '{"id":"e1"}' }),
      );
    });
    expect(result.current.events).toEqual([]);
    expect(result.current.status).toBe("connected");
  });

  it("kill switch '1' blocks EventSource — status disabled, buffer empty", async () => {
    localStorage.setItem("disable_live_events", "1");
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await new Promise((r) => setTimeout(r, 10));
    expect(MockEventSource.instances.length).toBe(0);
    expect(result.current.status).toBe("disabled");
    expect(result.current.events).toEqual([]);
  });

  it("kill switch '0' is NOT truthy — instance opens normally", async () => {
    localStorage.setItem("disable_live_events", "0");
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    expect(MockEventSource.instances.length).toBe(1);
  });

  it("kill switch removed — instance opens normally", async () => {
    localStorage.removeItem("disable_live_events");
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunEvents(RUN_A, { livePolling: true }),
      { wrapper: Wrapper },
    );
    await waitConnected(result);
    expect(MockEventSource.instances.length).toBe(1);
  });
});
