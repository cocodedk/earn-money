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
