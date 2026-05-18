import { describe, it, expect } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { lastSseInstance } from "../test/sseMock";
import { useScanRunEvents } from "./useScanRunEvents";

const sampleEvent = {
  id: "e1",
  scan_run_id: "r1",
  target_id: "t1",
  level: "info",
  event_type: "target_started",
  message: "Started",
  data: {},
  created_at: "2026-05-18T20:00:00.000000Z",
};

describe("useScanRunEvents", () => {
  it("opens an EventSource at the right URL on mount", async () => {
    renderHook(() => useScanRunEvents("r1"));
    await waitFor(() => expect(lastSseInstance()).toBeDefined());
    expect(lastSseInstance()!.url).toBe("/sse/scan-runs/r1/events/");
  });

  it("accumulates events in arrival order", async () => {
    const { result } = renderHook(() => useScanRunEvents("r1"));
    await waitFor(() => expect(lastSseInstance()).toBeDefined());
    act(() => {
      lastSseInstance()!.emit(sampleEvent);
      lastSseInstance()!.emit({ ...sampleEvent, id: "e2", message: "Done" });
    });
    expect(result.current.events).toHaveLength(2);
    expect(result.current.events[0].id).toBe("e1");
    expect(result.current.events[1].message).toBe("Done");
  });

  it("transitions status from connecting → open when EventSource opens", async () => {
    const { result } = renderHook(() => useScanRunEvents("r1"));
    expect(result.current.status).toBe("connecting");
    await waitFor(() => expect(result.current.status).toBe("open"));
  });

  it("marks status closed on error", async () => {
    const { result } = renderHook(() => useScanRunEvents("r1"));
    await waitFor(() => expect(result.current.status).toBe("open"));
    act(() => {
      lastSseInstance()!.error();
    });
    await waitFor(() => expect(result.current.status).toBe("closed"));
  });

  it("closes the source on unmount", async () => {
    const { unmount } = renderHook(() => useScanRunEvents("r1"));
    await waitFor(() => expect(lastSseInstance()).toBeDefined());
    const source = lastSseInstance()!;
    unmount();
    expect(source.readyState).toBe(2);
  });

  it("resets and reopens when scanRunId changes", async () => {
    const { rerender } = renderHook(
      ({ id }: { id: string }) => useScanRunEvents(id),
      { initialProps: { id: "r1" } },
    );
    await waitFor(() => expect(lastSseInstance()).toBeDefined());
    expect(lastSseInstance()!.url).toBe("/sse/scan-runs/r1/events/");
    rerender({ id: "r2" });
    await waitFor(() =>
      expect(lastSseInstance()!.url).toBe("/sse/scan-runs/r2/events/"),
    );
  });
});
