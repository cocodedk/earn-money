import { test } from "node:test";
import assert from "node:assert/strict";
import { loadProdScript } from "./_load.mjs";

loadProdScript("probe-status.js");

test("null turn -> in_progress", () => {
  assert.equal(window.getTurnStatus(null), "in_progress");
});

test("pending attempt + not complete -> in_progress", () => {
  const t = { attempts: [{ parseOutcome: "pending" }], complete: false };
  assert.equal(window.getTurnStatus(t), "in_progress");
});

test("single ok attempt + complete -> ok", () => {
  const t = { attempts: [{ parseOutcome: "ok" }], complete: true };
  assert.equal(window.getTurnStatus(t), "ok");
});

test("failed then ok -> recovered", () => {
  const t = {
    attempts: [{ parseOutcome: "failed" }, { parseOutcome: "ok" }],
    complete: true,
  };
  assert.equal(window.getTurnStatus(t), "recovered");
});

test("all failed -> parse_failed", () => {
  const t = {
    attempts: [{ parseOutcome: "failed" }, { parseOutcome: "failed" }],
    complete: true,
  };
  assert.equal(window.getTurnStatus(t), "parse_failed");
});

test("ok + policy denied -> policy_blocked (beats ok)", () => {
  const t = {
    attempts: [{ parseOutcome: "ok" }],
    policyDecision: { allowed: false },
    complete: true,
  };
  assert.equal(window.getTurnStatus(t), "policy_blocked");
});

test("recovered + policy denied -> policy_blocked (beats recovered)", () => {
  const t = {
    attempts: [{ parseOutcome: "failed" }, { parseOutcome: "ok" }],
    policyDecision: { allowed: false },
    complete: true,
  };
  assert.equal(window.getTurnStatus(t), "policy_blocked");
});

test("formatTurnStatus maps every enum value", () => {
  assert.equal(window.formatTurnStatus("ok"), "ok");
  assert.equal(window.formatTurnStatus("recovered"), "invalid_action → recovered");
  assert.equal(window.formatTurnStatus("parse_failed"), "parse_failed");
  assert.equal(window.formatTurnStatus("policy_blocked"), "policy_blocked");
  assert.equal(window.formatTurnStatus("in_progress"), "in_progress");
});
