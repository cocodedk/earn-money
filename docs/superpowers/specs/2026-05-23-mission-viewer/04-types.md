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
  mission_budget: number;
  consumed_budget: number;
  progress_counters: Record<string, number>;
  created_at: Iso8601;
  updated_at: Iso8601;
};
```

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
};
```

## AgentAction

```typescript
type ActionType =
  | "observe_page" | "navigate" | "click" | "fill_form"
  | "submit_form" | "http_request" | "run_stub" | "run_tool"
  | "inspect_asset" | "store_note" | "submit_candidate"
  | "request_verify" | "request_phase_transition" | "stop";

type ValidationStatus = "valid" | "denied" | "pending";
type ExecutionStatus = "pending" | "success" | "error";

type AgentAction = {
  id: Uuid;
  action_type: ActionType;
  goal: string;
  reason: string;
  hypothesis: string | null;
  args_redacted: Record<string, unknown>;
  validation_status: ValidationStatus;
  execution_status: ExecutionStatus;
  denial_reason: string | null;
  observations: AgentObservation[];
};
```

## AgentObservation

```typescript
type ObservationType = "page" | "http" | "stub" | "tool" | "asset";

type AgentObservation = {
  id: Uuid;
  observation_type: ObservationType;
  data: Record<string, unknown>;
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
  content: string;
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
