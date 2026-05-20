import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
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
  vi.useRealTimers();
  uninstall();
  localStorage.removeItem("disable_live_events");
});

async function mountConnected(opts: { autoOpenAfter?: boolean } = {}) {
  const { Wrapper } = makeRenderHookWrapper();
  const r = renderHook(() => useScanRunEvents(RUN_A, { livePolling: true }), {
    wrapper: Wrapper,
  });
  await waitConnected(r.result);
  // Switch to fake timers only after the first instance has opened — this
  // keeps the testing-library waitFor (used by waitConnected) on real timers.
  vi.useFakeTimers();
  // For backoff/polling-fallback tests, disable auto-open on subsequent
  // instances so the test can assert behaviour with no successful reopens.
  if (opts.autoOpenAfter === false) MockEventSource.autoOpen = false;
  return r;
}

async function flushReactUpdates() {
  // Let React commit state updates produced by SSE callbacks under fake timers.
  await act(async () => {
    await Promise.resolve();
  });
}

describe("useScanRunEvents — exponential-backoff reconnect", () => {
  it("first failure → status reconnecting, retry scheduled at 1s", async () => {
    const { result } = await mountConnected();
    act(() => lastInstance().fail());
    await flushReactUpdates();
    expect(result.current.status).toBe("reconnecting");
    expect(MockEventSource.instances.length).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(999);
    });
    expect(MockEventSource.instances.length).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(MockEventSource.instances.length).toBe(2);
  });

  it("backoff sequence 1s, 2s, 4s, 8s, 16s for attempts 0..4", async () => {
    const { result } = await mountConnected({ autoOpenAfter: false });
    const expected = [1000, 2000, 4000, 8000, 16000];
    for (let i = 0; i < expected.length; i += 1) {
      const before = MockEventSource.instances.length;
      act(() => lastInstance().fail());
      await flushReactUpdates();
      expect(result.current.status).toBe("reconnecting");

      await act(async () => {
        await vi.advanceTimersByTimeAsync(expected[i] - 1);
      });
      expect(MockEventSource.instances.length).toBe(before);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(MockEventSource.instances.length).toBe(before + 1);
    }
  });

  it("successful reopen resets attempt counter (next failure schedules at 1s again)", async () => {
    const { result } = await mountConnected();
    act(() => lastInstance().fail());
    await flushReactUpdates();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    // Drive the microtask-queued onopen on the reopened instance.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.status).toBe("connected");

    const before = MockEventSource.instances.length;
    act(() => lastInstance().fail());
    await flushReactUpdates();
    expect(result.current.status).toBe("reconnecting");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(999);
    });
    expect(MockEventSource.instances.length).toBe(before);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(MockEventSource.instances.length).toBe(before + 1);
  });

  it("5 consecutive failures with no successful open → polling-fallback, no further retry", async () => {
    const { result } = await mountConnected({ autoOpenAfter: false });
    const delays = [1000, 2000, 4000, 8000, 16000];
    for (let i = 0; i < delays.length; i += 1) {
      act(() => lastInstance().fail());
      await flushReactUpdates();
      expect(result.current.status).toBe("reconnecting");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(delays[i]);
      });
    }
    // After 5 reconnect attempts the last instance has been recreated but never
    // opened (we never advance the microtask to fire onopen). The next failure
    // should trip the polling-fallback gate.
    const before = MockEventSource.instances.length;
    act(() => lastInstance().fail());
    await flushReactUpdates();
    expect(result.current.status).toBe("polling-fallback");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(MockEventSource.instances.length).toBe(before);
  });

  it("manual reconnect() during backoff cancels pending retry, opens immediately, resets counter", async () => {
    const { result } = await mountConnected();
    act(() => lastInstance().fail());
    await flushReactUpdates();
    expect(result.current.status).toBe("reconnecting");

    const before = MockEventSource.instances.length;
    act(() => result.current.reconnect());
    await flushReactUpdates();
    expect(MockEventSource.instances.length).toBe(before + 1);

    // The originally-scheduled 1s retry should have been cancelled.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(MockEventSource.instances.length).toBe(before + 1);

    // Drive the microtask-queued onopen for the just-opened instance.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.status).toBe("connected");

    const beforeSecond = MockEventSource.instances.length;
    act(() => lastInstance().fail());
    await flushReactUpdates();
    expect(result.current.status).toBe("reconnecting");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(999);
    });
    expect(MockEventSource.instances.length).toBe(beforeSecond);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(MockEventSource.instances.length).toBe(beforeSecond + 1);
  });

  it("unmount during backoff cancels pending retry — no new instance", async () => {
    const { result, unmount } = await mountConnected();
    act(() => lastInstance().fail());
    await flushReactUpdates();
    expect(result.current.status).toBe("reconnecting");
    const before = MockEventSource.instances.length;
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(MockEventSource.instances.length).toBe(before);
  });
});
