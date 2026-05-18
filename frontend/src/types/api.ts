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

export type ScanEventLevel = "debug" | "info" | "warning" | "error";

export type ScanEvent = {
  id: Uuid;
  scan_run_id: Uuid;
  target_id: Uuid | null;
  level: ScanEventLevel;
  event_type: string;
  message: string;
  data: Record<string, unknown>;
  created_at: Iso8601;
};

export type Target = {
  id: Uuid;
  project: Uuid;
  base_url: string;
  host: string | null;
  ip: string | null;
  status: TargetStatus;
  created_at: Iso8601;
};

export type CreateTargetBody = {
  project: Uuid;
  base_url: string;
  host?: string | null;
  ip?: string | null;
  status?: TargetStatus;
};

export type StubStatus = "pending" | "in_progress" | "done";

export type Stub = {
  slug: string;
  phase: number;
  spec: number;
  title: string;
  status: StubStatus;
  fixture: string | null;
  category: string;
  phase_title: string;
  phase_slug: string;
  spec_slug: string;
  path: string;
};

export type StubDetail = Stub & {
  body: string;
};

export type ScanRun = {
  id: Uuid;
  project: Uuid;
  stub_slug: string;
  status: ScanRunStatus;
  target_run_count: number;
  findings_count: number;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
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

export type TargetRun = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  target_base_url: string;
  status: ScanRunStatus;
  findings_count: number;
  evidence_count: number;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
};
