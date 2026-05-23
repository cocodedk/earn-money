---
tier: FAST
depends_on: [01-types, 02-fixtures]
files:
  creates: [frontend/src/features/missions/describeTurn.ts, frontend/src/features/missions/describeTurn.test.ts]
  modifies: []
allow_extra_files: false
---

# Task 5: describeTurn

**Goal:** Pure function that maps a turn into plain-language text and a tone.

**Depends on:** [Task 1](01-types.md)

**Files:**
- Create: `frontend/src/features/missions/describeTurn.ts`
- Create: `frontend/src/features/missions/describeTurn.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/features/missions/describeTurn.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { describeTurn } from "./describeTurn";
import { makeTurn, makeAction } from "./__fixtures__/mission";

describe("describeTurn", () => {
  it("describes an executed observe_page action", () => {
    const turn = makeTurn({
      status: "completed",
      actions: [makeAction({
        action_type: "observe_page",
        goal: "Look at the home page",
        execution_status: "executed",
        validation_status: "valid",
      })],
    });
    const d = describeTurn(turn);
    expect(d.title).toBe("Look at the home page");
    expect(d.tone).toBe("success");
  });

  it("describes a denied action", () => {
    const turn = makeTurn({
      status: "action_denied",
      actions: [makeAction({
        action_type: "http_request",
        goal: "Send DELETE request",
        validation_status: "denied_roe",
        execution_status: "skipped",
        denial_reason: "Destructive methods not allowed",
      })],
    });
    const d = describeTurn(turn);
    expect(d.title).toBe("Send DELETE request");
    expect(d.result).toBe("Blocked: Destructive methods not allowed");
    expect(d.tone).toBe("denied");
  });

  it("describes a failed action", () => {
    const turn = makeTurn({
      status: "error",
      actions: [makeAction({
        action_type: "navigate",
        goal: "Navigate to /admin",
        execution_status: "failed",
        validation_status: "valid",
      })],
    });
    const d = describeTurn(turn);
    expect(d.title).toBe("Navigate to /admin");
    expect(d.tone).toBe("error");
  });

  it("describes a running turn", () => {
    const turn = makeTurn({
      status: "started",
      actions: [makeAction({
        action_type: "observe_page",
        goal: "Inspect login form",
        execution_status: "pending",
        validation_status: "valid",
      })],
    });
    const d = describeTurn(turn);
    expect(d.title).toBe("Inspect login form");
    expect(d.tone).toBe("running");
  });

  it("describes a turn with no actions yet", () => {
    const turn = makeTurn({ status: "started", actions: [] });
    const d = describeTurn(turn);
    expect(d.title).toBe("Thinking...");
    expect(d.tone).toBe("running");
  });

  it("describes a store_note action", () => {
    const turn = makeTurn({
      status: "completed",
      actions: [makeAction({
        action_type: "store_note",
        goal: "Remember that admin uses default creds",
        execution_status: "executed",
        validation_status: "valid",
      })],
    });
    const d = describeTurn(turn);
    expect(d.title).toBe("Remember that admin uses default creds");
    expect(d.tone).toBe("success");
  });

  it("describes a denied_budget action", () => {
    const turn = makeTurn({
      status: "action_denied",
      actions: [makeAction({
        action_type: "http_request",
        goal: "Probe endpoint",
        validation_status: "denied_budget",
        execution_status: "skipped",
        denial_reason: "Turn budget exhausted",
      })],
    });
    const d = describeTurn(turn);
    expect(d.result).toBe("Blocked: Turn budget exhausted");
    expect(d.tone).toBe("denied");
  });

  it("falls back for unknown action type", () => {
    const turn = makeTurn({
      status: "completed",
      actions: [makeAction({
        action_type: "some_future_action" as string,
        goal: "Do something new",
        execution_status: "executed",
        validation_status: "valid",
      })],
    });
    const d = describeTurn(turn);
    expect(d.title).toBe("Do something new");
    expect(d.tone).toBe("success");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/describeTurn.test.ts`
Expected: FAIL — `describeTurn` not found.

- [ ] **Step 3: Implement describeTurn**

Create `frontend/src/features/missions/describeTurn.ts`:

```typescript
import type { AgentAction, AgentTurn, TurnDescription } from "./types";

function toneFromAction(action: AgentAction): TurnDescription["tone"] {
  if (action.execution_status === "pending") return "running";
  if (action.execution_status === "failed") return "error";
  if (action.validation_status !== "valid") return "denied";
  if (action.execution_status === "executed") return "success";
  return "neutral";
}

function resultFromAction(action: AgentAction): string {
  if (action.validation_status !== "valid") {
    return action.denial_reason ? `Blocked: ${action.denial_reason}` : "Blocked by policy";
  }
  if (action.execution_status === "failed") {
    return "Action failed";
  }
  if (action.execution_status === "pending") {
    return "In progress...";
  }
  return "";
}

export function describeTurn(turn: AgentTurn): TurnDescription {
  const action = turn.actions[0];

  if (!action) {
    if (turn.status === "error") return { title: "Turn failed", result: "No action details recorded", tone: "error" };
    if (turn.status === "completed") return { title: "Turn completed", result: "No action details recorded", tone: "neutral" };
    return { title: "Thinking...", result: "", tone: "running" };
  }

  return {
    title: action.goal || `${action.action_type}`,
    result: resultFromAction(action),
    tone: toneFromAction(action),
  };
}
```

- [ ] **Step 4: Run tests** — `cd frontend && npx vitest run src/features/missions/describeTurn.test.ts` → PASS

- [ ] **Step 5: Commit** — `git add frontend/src/features/missions/describeTurn.ts frontend/src/features/missions/describeTurn.test.ts && git commit -m "feat(frontend): describeTurn — plain-language mapper for turn cards"`
