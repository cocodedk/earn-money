import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScanRunLiveEventsPanel } from "./ScanRunLiveEventsPanel";
import * as hookModule from "./useScanRunEvents";
import { makeEvent } from "./__fixtures__/event";
import {
  SCAN_RUN_ID,
  mockLiveEventsHook,
  renderLivePanel,
} from "./__fixtures__/livePanelMockHook";

vi.mock("./useScanRunEvents", () => ({ useScanRunEvents: vi.fn() }));

const TOGGLE = "events-autoscroll-toggle";

describe("ScanRunLiveEventsPanel — auto-scroll", () => {
  let scrollSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.mocked(hookModule.useScanRunEvents).mockReset();
    if (!("scrollIntoView" in Element.prototype)) {
      (Element.prototype as unknown as { scrollIntoView: () => void }).scrollIntoView =
        () => {};
    }
    scrollSpy = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.mocked(hookModule.useScanRunEvents).mockReset();
  });

  it("toggle button click flips state and label (on → off → on)", async () => {
    const user = userEvent.setup();
    mockLiveEventsHook("connected", [makeEvent({ id: "e1" })]);
    renderLivePanel();
    const btn = screen.getByTestId(TOGGLE);
    expect(btn.textContent).toBe("Auto-scroll: on");
    await user.click(btn);
    expect(btn.textContent).toBe("Auto-scroll: off");
    await user.click(btn);
    expect(btn.textContent).toBe("Auto-scroll: on");
  });

  it("with on and new event arriving → scrollIntoView called on last row", () => {
    mockLiveEventsHook("connected", [makeEvent({ id: "e1" })]);
    const { rerender } = renderLivePanel();
    scrollSpy.mockClear();

    mockLiveEventsHook("connected", [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
    ]);
    rerender(
      <ScanRunLiveEventsPanel scanRunId={SCAN_RUN_ID} livePolling={true} />,
    );
    expect(scrollSpy).toHaveBeenCalled();
    const calledOn = scrollSpy.mock.instances[0] as HTMLElement;
    expect(calledOn.getAttribute("data-testid")).toBe("event-row-e2");
    expect(scrollSpy.mock.calls[0][0]).toEqual({ block: "end" });
  });

  it("with off and new event arriving → spy NOT called", async () => {
    const user = userEvent.setup();
    mockLiveEventsHook("connected", [makeEvent({ id: "e1" })]);
    const { rerender } = renderLivePanel();
    await user.click(screen.getByTestId(TOGGLE));
    scrollSpy.mockClear();

    mockLiveEventsHook("connected", [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
    ]);
    rerender(
      <ScanRunLiveEventsPanel scanRunId={SCAN_RUN_ID} livePolling={true} />,
    );
    expect(scrollSpy).not.toHaveBeenCalled();
  });

  it("scroll event near bottom does not flip toggle", () => {
    mockLiveEventsHook("connected", [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
    ]);
    renderLivePanel();
    const container = screen.getByTestId("events-scroll-container");
    Object.defineProperty(container, "scrollHeight", {
      value: 500,
      configurable: true,
    });
    Object.defineProperty(container, "clientHeight", {
      value: 100,
      configurable: true,
    });
    Object.defineProperty(container, "scrollTop", {
      value: 400,
      configurable: true,
    });
    act(() => {
      fireEvent.scroll(container);
    });
    expect(screen.getByTestId(TOGGLE).textContent).toBe("Auto-scroll: on");
  });

  it("manual scroll up flips toggle to off; subsequent emit does not scroll", () => {
    mockLiveEventsHook("connected", [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
    ]);
    const { rerender } = renderLivePanel();
    const container = screen.getByTestId("events-scroll-container");
    Object.defineProperty(container, "scrollHeight", {
      value: 500,
      configurable: true,
    });
    Object.defineProperty(container, "clientHeight", {
      value: 100,
      configurable: true,
    });
    Object.defineProperty(container, "scrollTop", {
      value: 0,
      configurable: true,
    });
    act(() => {
      fireEvent.scroll(container);
    });
    expect(screen.getByTestId(TOGGLE).textContent).toBe("Auto-scroll: off");

    scrollSpy.mockClear();
    mockLiveEventsHook("connected", [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
      makeEvent({ id: "e3" }),
    ]);
    rerender(
      <ScanRunLiveEventsPanel scanRunId={SCAN_RUN_ID} livePolling={true} />,
    );
    expect(scrollSpy).not.toHaveBeenCalled();
  });
});
