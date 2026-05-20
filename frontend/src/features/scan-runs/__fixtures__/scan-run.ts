import type { ScanRun } from "../../../types/api";

const BASE: ScanRun = {
  id: "r-1",
  project: "p-1",
  stub_slug: "1.1",
  status: "queued",
  started_at: null,
  finished_at: null,
  target_run_count: 1,
  findings_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
  updated_at: "2026-05-19T08:00:00.000000Z",
};

export function makeScanRun(overrides: Partial<ScanRun> = {}): ScanRun {
  return { ...BASE, ...overrides };
}
