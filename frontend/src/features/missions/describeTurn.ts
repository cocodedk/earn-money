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
