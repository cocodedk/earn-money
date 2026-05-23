# Mission Viewer Plan — Task 1: Types and Fixtures

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define all Mission Viewer TypeScript types and test fixture factories.

**Architecture:** Types live in `features/missions/types.ts`, re-exported from `types/api.ts` where needed. Fixture factories in `features/missions/__fixtures__/mission.ts` follow the `makeScanRun()` pattern from scan-runs.

**Tech Stack:** TypeScript, Vitest

---

### Task 1: Types

**Files:**
- Create: `frontend/src/features/missions/types.ts`

- [ ] **Step 1: Create the types file**

```typescript
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
```

- [ ] **Step 2: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS — no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/missions/types.ts
git commit -m "feat(frontend): mission viewer types — session, turn, action, note"
```

---

### Task 2: Fixture factories

**Files:**
- Create: `frontend/src/features/missions/__fixtures__/mission.ts`

- [ ] **Step 1: Create fixture factories**

```typescript
import type {
  AgentAction,
  AgentNote,
  AgentObservation,
  AgentSession,
  AgentTurn,
} from "../types";

const SESSION_ID = "ssssssss-1111-1111-1111-111111111111";
const SCAN_RUN_ID = "rrrrrrrr-1111-1111-1111-111111111111";
const TARGET_ID = "tttttttt-1111-1111-1111-111111111111";

export function makeSession(
  over: Partial<AgentSession> = {},
): AgentSession {
  return {
    id: SESSION_ID,
    scan_run: SCAN_RUN_ID,
    target: TARGET_ID,
    target_base_url: "https://target.cocode.dk",
    target_host: "target.cocode.dk",
    status: "running",
    current_phase: "recon",
    active_phases: ["recon", "enumerate", "probe", "verify", "report"],
    autonomy_mode: "lab_free_run",
    mission_profile: "juice_shop_scoreboard",
    mission_budget: { max_turns: 25 },
    consumed_budget: { turns: 3, mission: { turns: 3 } },
    progress_counters: {},
    terminal_reason: null,
    started_at: "2026-05-23T10:00:00Z",
    finished_at: null,
    created_at: "2026-05-23T10:00:00Z",
    updated_at: "2026-05-23T10:01:00Z",
    ...over,
  };
}

export function makeObservation(
  over: Partial<AgentObservation> = {},
): AgentObservation {
  return {
    id: "oooooooo-1111-1111-1111-111111111111",
    observation_type: "page",
    data: { title: "Home Page" },
    artifact_refs: {},
    content_hash: "abc123",
    redactions: [],
    is_delta: false,
    created_at: "2026-05-23T10:00:05Z",
    ...over,
  };
}

export function makeAction(
  over: Partial<AgentAction> = {},
): AgentAction {
  return {
    id: "aaaaaaaa-1111-1111-1111-111111111111",
    action_type: "observe_page",
    goal: "Look at the home page",
    reason: "Starting reconnaissance",
    hypothesis: "The home page may reveal application structure",
    args_redacted: { url: "/" },
    validation_status: "valid",
    execution_status: "executed",
    denial_reason: "",
    executed_at: "2026-05-23T10:00:05Z",
    observations: [makeObservation()],
    created_at: "2026-05-23T10:00:04Z",
    updated_at: "2026-05-23T10:00:05Z",
    ...over,
  };
}

export function makeTurn(
  over: Partial<AgentTurn> = {},
): AgentTurn {
  return {
    id: "uuuuuuuu-1111-1111-1111-111111111111",
    index: 0,
    phase: "recon",
    status: "completed",
    model: "claude-sonnet-4-6",
    input_tokens: 1200,
    output_tokens: 350,
    cost_estimate: 0.005,
    actions: [makeAction()],
    created_at: "2026-05-23T10:00:03Z",
    updated_at: "2026-05-23T10:00:06Z",
    finished_at: "2026-05-23T10:00:06Z",
    ...over,
  };
}

export function makeNote(
  over: Partial<AgentNote> = {},
): AgentNote {
  return {
    id: "nnnnnnnn-1111-1111-1111-111111111111",
    turn: "uuuuuuuu-1111-1111-1111-111111111111",
    turn_index: 0,
    note_type: "hypothesis",
    content: { text: "Login form likely uses default credentials" },
    evidence_refs: [],
    created_at: "2026-05-23T10:00:06Z",
    ...over,
  };
}

export { SESSION_ID, SCAN_RUN_ID, TARGET_ID };
```

- [ ] **Step 2: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/missions/__fixtures__/mission.ts
git commit -m "test(frontend): mission viewer fixture factories"
```
