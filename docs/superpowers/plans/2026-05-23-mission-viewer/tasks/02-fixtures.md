---
tier: FAST
depends_on: [01-types]
files:
  creates: [frontend/src/features/missions/__fixtures__/mission.ts]
  modifies: []
allow_extra_files: false
---

# Task 2: Fixture Factories

**Goal:** Test fixture factories for all mission viewer types.

**Depends on:** [Task 1](01-types.md)

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
