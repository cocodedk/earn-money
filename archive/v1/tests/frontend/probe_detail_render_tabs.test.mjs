// Tab-behavior tests for probe-detail.js (delta + full tabs, click
// switching, whitelisted-heading delta). Each test resets state via
// probeReducer({stage:"probe_start"}) so they're independent.
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { freshPanel, find, findAll } from "./_probe_detail_render_helpers.mjs";

beforeEach(() => {
  window.probeReducer({ stage: "probe_start" });
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
