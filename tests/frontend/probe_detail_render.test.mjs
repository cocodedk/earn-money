// DOM-rendering tests for probe-detail.js. Uses the minimal DOM shim
// from _load.mjs — no jsdom dependency. Each test resets state via
// probeReducer({stage:"probe_start"}) so they're independent.
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { loadProdScript, installDomShim } from "./_load.mjs";

installDomShim();
loadProdScript("probe-status.js");
loadProdScript("probe-state.js");
loadProdScript("probe-detail.js");

function freshPanel() {
  installDomShim();
  const panel = document.createElement("aside");
  document._register("probe-detail", panel);
  return panel;
}

beforeEach(() => {
  window.probeReducer({ stage: "probe_start" });
});

function find(root, predicate) {
  if (predicate(root)) return root;
  for (const c of root._children || []) {
    const hit = find(c, predicate);
    if (hit) return hit;
  }
  return null;
}

function findAll(root, predicate, acc = []) {
  if (predicate(root)) acc.push(root);
  for (const c of root._children || []) findAll(c, predicate, acc);
  return acc;
}

test("renderDetailPanel renders 'Waiting for first turn…' when no turn selected", () => {
  const panel = freshPanel();
  window.renderDetailPanel();
  const waiting = find(panel, (n) => n.textContent === "Waiting for first turn…");
  assert.ok(waiting);
});

test("renderDetailPanel does nothing when #probe-detail is missing", () => {
  installDomShim();  // no probe-detail registered
  window.renderDetailPanel();  // should not throw
});

test("renderDetailPanel shows runError banner when set", () => {
  const panel = freshPanel();
  window.probeReducer({ stage: "probe_error", message: "boom" });
  window.renderDetailPanel();
  const banner = find(panel, (n) => /Probe error: boom/.test(n.textContent || ""));
  assert.ok(banner);
});

test("renderDetailPanel renders header + tabs + prompt + attempts for selected turn", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "SYS", prompt: "P", raw: "R", model: "m",
  });
  window.probeReducer({
    stage: "action_parsed", turn: 1, attempt: 1, action: {}, parse_recovered: false,
  });
  window.probeReducer({ stage: "complete", turn: 1, outcome: "completed" });
  window.renderDetailPanel();
  // Header has "TURN 1"
  assert.ok(find(panel, (n) => n.textContent === "TURN 1"));
  // Tabs has both delta + full
  assert.ok(find(panel, (n) => n.textContent === "delta"));
  assert.ok(find(panel, (n) => n.textContent === "full"));
  // Attempt card status row shows ✓ parsed
  assert.ok(find(panel, (n) => /✓ parsed/.test(n.textContent || "")));
  // Prompt shows up somewhere
  assert.ok(find(panel, (n) => n.tagName === "pre"
    && (n.textContent || "").includes("P")));
});

test("renderDetailPanel attempt card shows parse_failed with parseError", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "p", raw: "{", model: "m",
  });
  window.probeReducer({
    stage: "action_parse_failed", turn: 1, attempt: 1, error: "Expecting value",
  });
  window.renderDetailPanel();
  assert.ok(find(panel, (n) => /⚠ parse failed: Expecting value/.test(n.textContent || "")));
});

test("renderDetailPanel pending attempt shows … pending", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "p", raw: "{", model: "m",
  });
  window.renderDetailPanel();
  assert.ok(find(panel, (n) => /… pending/.test(n.textContent || "")));
});

test("renderDetailPanel shows retry badge when attempts.length > 1", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "p", raw: "{", model: "m",
  });
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 2,
    used_response_format: false, system: "s", prompt: "p", raw: "ok", model: "m",
  });
  window.renderDetailPanel();
  assert.ok(find(panel, (n) => n.className === "probe-detail-retry-badge"));
});

test("renderDetailPanel shows follow-latest button when followLatest=false", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "p", raw: "", model: "m",
  });
  window.setSelectedTurn(1);  // disables followLatest
  window.renderDetailPanel();
  const btn = find(panel, (n) => n.className === "probe-detail-follow-latest");
  assert.ok(btn);
  btn._click();
  assert.equal(window.probeState.followLatest, true);
});

test("Delta tab on first turn shows 'first turn — no delta' label", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "p", raw: "", model: "m",
  });
  window.renderDetailPanel();
  assert.ok(find(panel, (n) => n.textContent === "first turn — no delta"));
});

test("Delta tab shows 'could not compute delta' when prev/curr unsplittable", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "plain text", raw: "", model: "m",
  });
  window.probeReducer({
    stage: "action_pending", turn: 2, attempt: 1,
    used_response_format: true, system: "s", prompt: "still plain", raw: "", model: "m",
  });
  window.renderDetailPanel();
  assert.ok(find(panel, (n) => n.textContent === "could not compute delta"));
});

test("Full tab renders system + prompt concatenated", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "SYSDATA", prompt: "PROMPTDATA", raw: "", model: "m",
  });
  window.setActiveTab("full");
  window.renderDetailPanel();
  const pre = find(panel, (n) => n.tagName === "pre"
    && (n.textContent || "").includes("SYSDATA")
    && (n.textContent || "").includes("PROMPTDATA"));
  assert.ok(pre);
});

test("clicking a tab button updates activeTab via setActiveTab", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "p", raw: "", model: "m",
  });
  window.renderDetailPanel();
  const fullBtn = find(panel, (n) => n.textContent === "full");
  fullBtn._click();
  assert.equal(window.probeState.activeTab, "full");
});

test("attempt card 'with response_format' / 'without response_format' label", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "p", raw: "{", model: "m",
  });
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 2,
    used_response_format: false, system: "s", prompt: "p", raw: "ok", model: "m",
  });
  window.renderDetailPanel();
  assert.ok(find(panel, (n) => /Attempt #1 · with response_format/.test(n.textContent || "")));
  assert.ok(find(panel, (n) => /Attempt #2 · without response_format/.test(n.textContent || "")));
});

test("renderDetailPanel clears previous render before redrawing", () => {
  const panel = freshPanel();
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: "p", raw: "", model: "m",
  });
  window.renderDetailPanel();
  const firstCount = panel._children.length;
  window.renderDetailPanel();  // second call: should not double the children
  assert.equal(panel._children.length, firstCount);
});

test("Delta tab on turn 2 with whitelisted headings renders only diff section", () => {
  const panel = freshPanel();
  const prev =
    "intro\n=== Rules of Engagement ===\nroe1\n=== Session State ===\nsess1\n=== Available actions ===\nact1\n";
  const curr =
    "intro\n=== Rules of Engagement ===\nroe1\n=== Session State ===\nsess2\n=== Available actions ===\nact1\n";
  window.probeReducer({
    stage: "action_pending", turn: 1, attempt: 1,
    used_response_format: true, system: "s", prompt: prev, raw: "", model: "m",
  });
  window.probeReducer({
    stage: "action_pending", turn: 2, attempt: 1,
    used_response_format: true, system: "s", prompt: curr, raw: "", model: "m",
  });
  window.renderDetailPanel();
  const pre = findAll(panel, (n) => n.tagName === "pre")[0];
  assert.match(pre.textContent, /sess2/);
  assert.doesNotMatch(pre.textContent, /roe1/);
});
