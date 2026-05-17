import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { loadProdScript } from "./_load.mjs";

loadProdScript("probe-status.js");
loadProdScript("probe-state.js");

function reset() {
  window.probeReducer({ stage: "probe_start" });
}
beforeEach(reset);

const evt = (stage, data) => ({ stage, ...data });
const pending1 = (turn = 1) => evt("action_pending", {
  turn, attempt: 1, used_response_format: true,
  system: "s", prompt: "p", raw: "{", model: "m",
});
const pending2 = (turn = 1) => evt("action_pending", {
  turn, attempt: 2, used_response_format: false,
  system: "s", prompt: "p", raw: "ok", model: "m",
});

// ── reducer: attempt matching ─────────────────────────────────────────

test("action_pending appends pending attempt", () => {
  window.probeReducer(pending1());
  const t = window.probeState.turns[1];
  assert.equal(t.attempts.length, 1);
  assert.equal(t.attempts[0].parseOutcome, "pending");
  assert.equal(t.attempts[0].attempt, 1);
  assert.equal(t.attempts[0].parseError, null);
  assert.equal(t.system, "s");
  assert.equal(t.prompt, "p");
});

test("action_parse_failed flips matching attempt to failed", () => {
  window.probeReducer(pending1());
  window.probeReducer(evt("action_parse_failed", { turn: 1, attempt: 1, error: "boom" }));
  const a = window.probeState.turns[1].attempts[0];
  assert.equal(a.parseOutcome, "failed");
  assert.equal(a.parseError, "boom");
  assert.equal(window.probeState.turns[1].attempts.length, 1);
});

test("second action_pending appends attempt 2 without touching attempt 1", () => {
  window.probeReducer(pending1());
  window.probeReducer(evt("action_parse_failed", { turn: 1, attempt: 1, error: "boom" }));
  window.probeReducer(pending2());
  const t = window.probeState.turns[1];
  assert.equal(t.attempts.length, 2);
  assert.equal(t.attempts[0].parseOutcome, "failed");
  assert.equal(t.attempts[1].parseOutcome, "pending");
});

test("action_parsed flips only the matching attempt to ok", () => {
  window.probeReducer(pending1());
  window.probeReducer(evt("action_parse_failed", { turn: 1, attempt: 1, error: "boom" }));
  window.probeReducer(pending2());
  window.probeReducer(evt("action_parsed", { turn: 1, attempt: 2, action: {}, parse_recovered: true }));
  const t = window.probeState.turns[1];
  assert.equal(t.attempts[0].parseOutcome, "failed");
  assert.equal(t.attempts[1].parseOutcome, "ok");
  assert.equal(window.getTurnStatus(t), "recovered");
});

// ── selection / follow-latest ─────────────────────────────────────────

test("setSelectedTurn disables followLatest", () => {
  window.setSelectedTurn(2);
  assert.equal(window.probeState.selectedTurn, 2);
  assert.equal(window.probeState.followLatest, false);
});

test("after manual select, new action_pending does NOT change selectedTurn", () => {
  window.probeReducer(pending1(1));
  window.setSelectedTurn(1);
  window.probeReducer(pending1(3));
  assert.equal(window.probeState.selectedTurn, 1);
});

test("setFollowLatest(true) jumps to latest turn", () => {
  window.probeReducer(pending1(1));
  window.probeReducer(pending1(2));
  window.setSelectedTurn(1);
  window.setFollowLatest(true);
  assert.equal(window.probeState.selectedTurn, 2);
});

test("setActiveTab updates state", () => {
  window.setActiveTab("full");
  assert.equal(window.probeState.activeTab, "full");
});

// ── run-level ─────────────────────────────────────────────────────────

test("probe_error sets runError without touching turns", () => {
  window.probeReducer(pending1());
  window.probeReducer({ stage: "probe_error", message: "boom" });
  assert.equal(window.probeState.runError, "boom");
  assert.ok(window.probeState.turns[1]);
});

test("probe_start clears all state", () => {
  window.probeReducer(pending1());
  window.setSelectedTurn(1);
  window.probeReducer({ stage: "probe_error", message: "boom" });
  window.probeReducer({ stage: "probe_start" });
  assert.deepEqual(window.probeState.turns, {});
  assert.equal(window.probeState.selectedTurn, null);
  assert.equal(window.probeState.followLatest, true);
  assert.equal(window.probeState.runError, null);
});

// ── policy / observation / complete ───────────────────────────────────

test("policy event sets turn.policyDecision", () => {
  window.probeReducer(pending1());
  window.probeReducer(evt("policy", { turn: 1, action: {}, policy: { allowed: false, reason: "denied" } }));
  assert.deepEqual(window.probeState.turns[1].policyDecision, { allowed: false, reason: "denied" });
});

test("observation event sets turn.observation", () => {
  window.probeReducer(pending1());
  window.probeReducer(evt("observation", { turn: 1, obs: { status: 200, url: "u" } }));
  assert.deepEqual(window.probeState.turns[1].observation, { status: 200, url: "u" });
});

test("complete event sets turn.complete", () => {
  window.probeReducer(pending1());
  window.probeReducer(evt("complete", { turn: 1, outcome: "completed" }));
  assert.equal(window.probeState.turns[1].complete, true);
});

// ── robustness ────────────────────────────────────────────────────────

test("unknown stage is ignored silently", () => {
  const before = JSON.stringify(window.probeState);
  window.probeReducer({ stage: "totally_unknown" });
  assert.equal(JSON.stringify(window.probeState), before);
});

test("onChange fires once per accepted event, zero for unknown", () => {
  let count = 0;
  window.onChange(() => count++);
  window.probeReducer(pending1());
  assert.equal(count, 1);
  window.probeReducer({ stage: "totally_unknown" });
  assert.equal(count, 1);
});

test("followLatest auto-selects new turn when enabled", () => {
  window.probeReducer(pending1(1));
  assert.equal(window.probeState.selectedTurn, 1);
  window.probeReducer(pending1(2));
  assert.equal(window.probeState.selectedTurn, 2);
});

// ── maxTurn cached invariant (perf fix in commit 6732f3b) ─────────────

test("maxTurn starts at 0 in fresh state", () => {
  assert.equal(window.probeState.maxTurn, 0);
});

test("maxTurn tracks the highest turn number seen on action_pending", () => {
  window.probeReducer(pending1(1));
  assert.equal(window.probeState.maxTurn, 1);
  window.probeReducer(pending1(3));
  assert.equal(window.probeState.maxTurn, 3);
  window.probeReducer(pending1(2));   // out-of-order event must NOT decrease maxTurn
  assert.equal(window.probeState.maxTurn, 3);
});

test("probe_start resets maxTurn to 0", () => {
  window.probeReducer(pending1(5));
  assert.equal(window.probeState.maxTurn, 5);
  window.probeReducer({ stage: "probe_start" });
  assert.equal(window.probeState.maxTurn, 0);
});

test("setFollowLatest(true) before any turn is a no-op on selectedTurn", () => {
  window.setFollowLatest(true);
  assert.equal(window.probeState.selectedTurn, null);
});
