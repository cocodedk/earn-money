import { vi } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { ScanRunLiveEventsPanel } from "../ScanRunLiveEventsPanel";
import * as hookModule from "../useScanRunEvents";
import type {
  ConnectionStatus,
  UseScanRunEventsResult,
} from "../useScanRunEvents.utils";
import type { Event as ApiEvent } from "../../../types/api";

export const SCAN_RUN_ID = "11111111-1111-1111-1111-111111111111";

export function mockLiveEventsHook(
  status: ConnectionStatus,
  events: ApiEvent[],
): { reconnect: ReturnType<typeof vi.fn>; clear: ReturnType<typeof vi.fn> } {
  const reconnect = vi.fn();
  const clear = vi.fn();
  const result: UseScanRunEventsResult = {
    events,
    status,
    reconnect,
    clear,
  };
  vi.mocked(hookModule.useScanRunEvents).mockReturnValue(result);
  return { reconnect, clear };
}

export function renderLivePanel() {
  return renderWithProviders(
    <ScanRunLiveEventsPanel scanRunId={SCAN_RUN_ID} livePolling={true} />,
  );
}
