import type { Iso8601, Uuid } from "../../types/api";

export type AgentSessionStatus =
  | "pending" | "running" | "paused"
  | "completed" | "failed" | "stopped";

export type AgentPhase =
  | "recon" | "enumerate" | "probe" | "verify" | "report";

export type AutonomyMode = "lab_free_run" | "real_checkpointed";

export type BudgetLimits = {
  max_turns?: number;
  max_runtime_seconds?: number;
  max_llm_calls?: number;
  max_http_requests?: number;
  max_browser_actions?: number;
  max_asset_inspections?: number;
  [key: string]: number | undefined;
};

export type BudgetCounters = {
  turns?: number;
  llm_calls?: number;
  http_requests?: number;
  browser_actions?: number;
  asset_inspections?: number;
  [key: string]: number | undefined;
};

export type BudgetSnapshot = {
  turns?: number;
  llm_calls?: number;
  http_requests?: number;
  browser_actions?: number;
  asset_inspections?: number;
  mission?: BudgetCounters;
  phase?: BudgetCounters;
  [key: string]: number | BudgetCounters | undefined;
};

export type AgentSession = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  target_base_url: string;
  target_host: string;
  status: AgentSessionStatus;
  current_phase: AgentPhase;
  active_phases: AgentPhase[];
  autonomy_mode: AutonomyMode;
  mission_profile: string;
  mission_budget: BudgetLimits;
  consumed_budget: BudgetSnapshot;
  progress_counters: Record<string, number>;
  terminal_reason?: string | null;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type TurnStatus =
  | "started" | "action_proposed" | "action_denied"
  | "action_executed" | "completed" | "error";

export type AgentTurn = {
  id: Uuid;
  index: number;
  phase: AgentPhase;
  status: TurnStatus;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_estimate: number | null;
  actions: AgentAction[];
  created_at: Iso8601;
  updated_at: Iso8601;
  finished_at: Iso8601 | null;
};

export type KnownActionType =
  | "observe_page" | "navigate" | "click" | "fill_form"
  | "submit_form" | "http_request" | "run_stub" | "run_tool"
  | "inspect_asset" | "store_note" | "submit_candidate"
  | "request_verify" | "request_phase_transition"
  | "diff_response" | "compare_baseline" | "stop";

export type ActionType = KnownActionType | (string & {});

export type ValidationStatus =
  | "valid" | "invalid_schema" | "denied_phase"
  | "denied_roe" | "denied_budget" | "denied_scope";

export type ExecutionStatus =
  | "pending" | "skipped" | "executed" | "failed";

export type ObservationType = "page" | "http" | "stub" | "tool" | "asset";

export type AgentObservation = {
  id: Uuid;
  observation_type: ObservationType;
  data: Record<string, unknown>;
  artifact_refs: Record<string, unknown>;
  content_hash: string;
  redactions: unknown[];
  is_delta: boolean;
  created_at: Iso8601;
};

export type AgentAction = {
  id: Uuid;
  action_type: ActionType;
  goal: string;
  reason: string;
  hypothesis: string;
  args_redacted: Record<string, unknown>;
  validation_status: ValidationStatus;
  execution_status: ExecutionStatus;
  denial_reason: string;
  executed_at: Iso8601 | null;
  observations: AgentObservation[];
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type NoteType =
  | "hypothesis" | "gap" | "credential_label"
  | "route" | "parameter" | "candidate";

export type AgentNote = {
  id: Uuid;
  turn: Uuid;
  turn_index: number;
  note_type: NoteType;
  content: Record<string, unknown>;
  evidence_refs: unknown[];
  created_at: Iso8601;
};

export type TurnDescription = {
  title: string;
  result: string;
  tone: "success" | "denied" | "error" | "running" | "neutral";
};

export type AgentEventData = {
  session_id: Uuid;
  turn_index?: number;
  action_type?: ActionType;
  note_type?: NoteType;
  reason?: string;
  status?: AgentSessionStatus;
  budget_snapshot?: BudgetSnapshot;
};

export function isTerminalStatus(s: AgentSessionStatus): boolean {
  return s === "completed" || s === "failed" || s === "stopped";
}
