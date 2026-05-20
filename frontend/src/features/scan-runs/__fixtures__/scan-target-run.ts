import type { ScanTargetRun } from "../../../types/api";

export function makeScanTargetRun(over: Partial<ScanTargetRun> = {}): ScanTargetRun {
  return {
    id: "tr-1",
    target: "t-1",
    target_base_url: "https://example.test",
    target_host: "example.test",
    status: "queued",
    started_at: null,
    finished_at: null,
    updated_at: "2026-05-19T00:00:00Z",
    findings_count: 0,
    evidence_count: 0,
    created_at: "2026-05-19T00:00:00Z",
    ...over,
  };
}
