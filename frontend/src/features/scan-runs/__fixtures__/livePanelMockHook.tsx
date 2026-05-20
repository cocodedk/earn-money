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
): void {
  const result: UseScanRunEventsResult = {
    events,
    status,
    reconnect: vi.fn(),
    clear: vi.fn(),
  };
  vi.mocked(hookModule.useScanRunEvents).mockReturnValue(result);
}

export function renderLivePanel() {
  return renderWithProviders(
    <ScanRunLiveEventsPanel scanRunId={SCAN_RUN_ID} livePolling={true} />,
  );
}
