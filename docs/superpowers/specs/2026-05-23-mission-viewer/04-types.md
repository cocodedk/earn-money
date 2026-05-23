# Mission Viewer — Types

All types in `features/missions/types.ts`.  Also registered in
`types/api.ts` if shared across features.

## AgentSession

```typescript
type AgentSessionStatus =
  | "pending" | "running" | "paused"
  | "completed" | "failed" | "stopped";

type AgentPhase =
  | "recon" | "enumerate" | "probe" | "verify" | "report";

type AutonomyMode = "lab_free_run" | "real_checkpointed";

type BudgetLimits = {
  max_turns?: number;
  max_runtime_seconds?: number;
  max_llm_calls?: number;
  max_http_requests?: number;
  max_browser_actions?: number;
  max_asset_inspections?: number;
  [key: string]: number | undefined;
};

type BudgetCounters = {
  turns?: number;
  llm_calls?: number;
  http_requests?: number;
  browser_actions?: number;
  asset_inspections?: number;
  [key: string]: number | undefined;
};

type BudgetSnapshot = {
  turns?: number;
  llm_calls?: number;
  http_requests?: number;
  browser_actions?: number;
  asset_inspections?: number;
  mission?: BudgetCounters;
  phase?: BudgetCounters;
  [key: string]: number | BudgetCounters | undefined;
};

type AgentSession = {
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
```

The top-strip turn counter reads:

```typescript
const usedTurns =
  consumed_budget.mission?.turns ?? consumed_budget.turns ?? 0;
const maxTurns = mission_budget.max_turns;
```

If `maxTurns` is absent, render "`N` turns used".

## AgentTurn

```typescript
type TurnStatus =
  | "started" | "action_proposed" | "action_denied"
  | "action_executed" | "completed" | "error";

type AgentTurn = {
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
```

## AgentAction

```typescript
type KnownActionType =
  | "observe_page" | "navigate" | "click" | "fill_form"
  | "submit_form" | "http_request" | "run_stub" | "run_tool"
  | "inspect_asset" | "store_note" | "submit_candidate"
  | "request_verify" | "request_phase_transition"
  | "diff_response" | "compare_baseline" | "stop";

type ActionType = KnownActionType | (string & {});

type ValidationStatus =
  | "valid" | "invalid_schema" | "denied_phase"
  | "denied_roe" | "denied_budget" | "denied_scope";

type ExecutionStatus =
  | "pending" | "skipped" | "executed" | "failed";

type AgentAction = {
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
```

## AgentObservation

```typescript
type ObservationType = "page" | "http" | "stub" | "tool" | "asset";

type AgentObservation = {
  id: Uuid;
  observation_type: ObservationType;
  data: Record<string, unknown>;
  artifact_refs: Record<string, unknown>;
  content_hash: string;
  redactions: unknown[];
  is_delta: boolean;
  created_at: Iso8601;
};
```

## AgentNote

```typescript
type NoteType =
  | "hypothesis" | "gap" | "credential_label"
  | "route" | "parameter" | "candidate";

type AgentNote = {
  id: Uuid;
  turn: Uuid;
  turn_index: number;
  note_type: NoteType;
  content: Record<string, unknown>;
  evidence_refs: unknown[];
  created_at: Iso8601;
};
```

## describeTurn output

```typescript
type TurnDescription = {
  title: string;   // "Looked at the home page"
  result: string;  // "Found a login form"
  tone: "success" | "denied" | "error" | "running" | "neutral";
};
```

## Agent event payloads

```typescript
type AgentEventData = {
  session_id: Uuid;
  turn_index?: number;
  action_type?: ActionType;
  note_type?: NoteType;
  reason?: string;
  status?: AgentSessionStatus;
  budget_snapshot?: BudgetSnapshot;
};
```

The wrapper treats unknown extra keys as opaque raw event data for the
Details disclosure only.  It never relies on raw event data to build the
canonical turn list.
