// Shared pure helpers: getTurnStatus + formatTurnStatus.
// Loaded BEFORE probe-state.js, probe-render.js, probe-detail.js so both
// renderers can call into them without depending on the detail panel.
// No DOM access. No state mutation.

window.getTurnStatus = function getTurnStatus(turn) {
  if (!turn) return "in_progress";

  // Policy block beats parse outcomes — operator cares "was this blocked?"
  // even if the LLM call itself parsed cleanly.
  if (turn.policyDecision && turn.policyDecision.allowed === false) {
    return "policy_blocked";
  }

  const attempts = turn.attempts || [];
  const hasOk      = attempts.some((a) => a.parseOutcome === "ok");
  const hasFailed  = attempts.some((a) => a.parseOutcome === "failed");
  const hasPending = attempts.some((a) => a.parseOutcome === "pending");

  if (hasPending && !turn.complete) return "in_progress";
  if (hasOk && hasFailed)           return "recovered";
  if (hasOk)                        return "ok";
  if (hasFailed)                    return "parse_failed";

  return "in_progress";
};

const _STATUS_DISPLAY = {
  "ok":             "ok",
  "recovered":      "invalid_action → recovered",
  "parse_failed":   "parse_failed",
  "policy_blocked": "policy_blocked",
  "in_progress":    "in_progress",
};

window.formatTurnStatus = function formatTurnStatus(status) {
  return _STATUS_DISPLAY[status] || status;
};
