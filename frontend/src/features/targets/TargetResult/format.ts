// Local formatting helpers for TargetResult child panels.
// Mirrors fmt/dash patterns also used by ScanRun*Panel; a project-wide
// extraction is tracked as a deferred follow-up in the 6D spec-review.

export function fmtDate(ts: string): string {
  return ts.slice(0, 10);
}

export function fmtDateTime(ts: string | null): string {
  return ts ? ts.slice(0, 19) : "—";
}

export function dash(v: string | null): string {
  return v || "—";
}
