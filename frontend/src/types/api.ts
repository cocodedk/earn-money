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
