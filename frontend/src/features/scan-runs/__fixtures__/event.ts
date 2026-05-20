import type { Event } from "../../../types/api";

export function makeEvent(over: Partial<Event> = {}): Event {
  return {
    id: "dddddddd-3333-3333-3333-333333333333",
    type: "target_started",
    scan_run: "11111111-1111-1111-1111-111111111111",
    target: "22222222-2222-2222-2222-222222222222",
    subject_type: "scan_target_run",
    subject_id: "22222222-2222-2222-2222-222222222222",
    level: "info",
    message: "Started target",
    data: {},
    created_at: "2026-05-20T08:00:00Z",
    ...over,
  };
}
