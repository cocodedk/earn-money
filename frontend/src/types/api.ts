export type Iso8601 = string;
export type Uuid = string;

export type ScanRunStatus =
  | "queued"
  | "running"
  | "paused"
  | "stopping"
  | "stopped"
  | "failed"
  | "done";

export type TargetStatus = "active" | "retired";

export type Severity = "info" | "low" | "medium" | "high" | "critical";

export type Project = {
  id: Uuid;
  name: string;
  description: string;
  target_count: number;
  scan_run_count: number;
  created_at: Iso8601;
};

export type CreateProjectBody = {
  name: string;
  description: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type HealthResponse = {
  status: "ok" | "degraded" | "down";
  db: boolean;
  redis?: boolean;
  worker?: boolean;
  version?: string;
};

export type Target = {
  id: Uuid;
  project: Uuid;
  base_url: string;
  host: string;
  ip: string | null;
  status: TargetStatus;
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type CreateTargetBody = {
  project: Uuid;
  base_url: string;
  host?: string;
  ip?: string | null;
};

export type StubStatus = "pending" | "in-progress" | "blocked" | "done";

export type StubSummary = {
  slug: string;
  phase: number;
  spec: number;
  phase_slug: string;
  spec_slug: string;
  title: string;
  phase_title: string;
  category: string;
  status: StubStatus;
  fixture: string;
  path: string;
};

export type Stub = StubSummary & { body: string };

export type ScanRun = {
  id: Uuid;
  project: Uuid;
  stub_slug: string;
  status: ScanRunStatus;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
  target_run_count: number;
  findings_count: number;
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type ScanTargetRun = {
  id: Uuid;
  target: Uuid;
  target_base_url: string;
  target_host: string;
  status: ScanRunStatus;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
  updated_at: Iso8601;
  findings_count: number;
  evidence_count: number;
  created_at: Iso8601;
};

export type CreateScanRunBody = {
  project: Uuid;
  stub_slug: string;
  target_ids: Uuid[];
};

export type LifecycleAction = "start" | "pause" | "resume" | "stop";

export type Confidence = "low" | "medium" | "high";

export type FindingStatus = "candidate" | "confirmed" | "rejected" | "stale";

export type Finding = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  stub_slug: string;
  title: string;
  category: string;
  severity: Severity;
  confidence: Confidence;
  status: FindingStatus;
  data: Record<string, unknown>;
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type Evidence = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  finding: Uuid | null;
  source: string;
  url: string | null;
  method: string | null;
  field: string | null;
  matched_value: string | null;
  raw_excerpt: string | null;
  content_hash: string;
  data: Record<string, unknown>;
  created_at: Iso8601;
};

export type EventLevel = "debug" | "info" | "warning" | "error";

export type Event = {
  id: Uuid;
  type: string;
  scan_run: Uuid;
  target: Uuid | null;
  subject_type: string;
  subject_id: Uuid;
  level: EventLevel;
  message: string;
  data: Record<string, unknown>;
  created_at: Iso8601;
};
