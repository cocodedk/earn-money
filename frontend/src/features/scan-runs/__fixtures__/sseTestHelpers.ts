import { act, renderHook, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { MockEventSource } from "../../../test/sseMock";
import { makeRenderHookWrapper } from "../../../test/renderWithProviders";
import { useScanRunEvents } from "../useScanRunEvents";

export const RUN_A = "11111111-1111-1111-1111-111111111111";
export const RUN_B = "22222222-2222-2222-2222-222222222222";

export function lastInstance(): MockEventSource {
  const arr = MockEventSource.instances;
  return arr[arr.length - 1];
}

export async function waitConnected(result: {
  current: { status: string };
}): Promise<void> {
  await waitFor(() => {
    if (result.current.status !== "connected") {
      throw new Error(`status=${result.current.status}`);
    }
  });
}

export async function flushReactUpdates(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
  });
}

const FALLBACK_DELAYS = [1000, 2000, 4000, 8000, 16000];

/**
 * Drives the hook into the `polling-fallback` state: mounts with livePolling,
 * waits for connected, then triggers 5 SSE failures followed by the
 * gate-tripping 6th failure. Returns the renderHook result.
 *
 * Switches Vitest to fake timers after the first successful connect — same
 * pattern as the reconnect tests.
 */
export async function mountAndEnterFallback(options?: { maxBuffer?: number }) {
  const { Wrapper } = makeRenderHookWrapper();
  const r = renderHook(
    () => useScanRunEvents(RUN_A, { livePolling: true, ...options }),
    { wrapper: Wrapper },
  );
  await waitConnected(r.result);
  vi.useFakeTimers();
  MockEventSource.autoOpen = false;
  for (let i = 0; i < FALLBACK_DELAYS.length; i += 1) {
    act(() => lastInstance().fail());
    await flushReactUpdates();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FALLBACK_DELAYS[i]);
    });
  }
  act(() => lastInstance().fail());
  await flushReactUpdates();
  return r;
}
