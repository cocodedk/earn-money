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

export type CreateScanRunBody = {
  project: Uuid;
  stub_slug: string;
  target_ids: Uuid[];
};

export type LifecycleAction = "start" | "pause" | "resume" | "stop";
