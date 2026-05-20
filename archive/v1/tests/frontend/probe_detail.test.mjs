import { test } from "node:test";
import assert from "node:assert/strict";
import { loadProdScript } from "./_load.mjs";

loadProdScript("probe-status.js");
loadProdScript("probe-state.js");
// probe-detail.js exposes splitPromptSections on window for testability.
loadProdScript("probe-detail.js");

const KNOWN = [
  "=== Rules of Engagement ===",
  "=== Session State ===",
  "=== Available actions ===",
];

test("splitPromptSections splits on known headings", () => {
  const prompt =
    "system intro\n" +
    "=== Rules of Engagement ===\nroe body\n" +
    "=== Session State ===\nsess body\n" +
    "=== Available actions ===\nactions body\n";
  const out = window.splitPromptSections(prompt, KNOWN);
  assert.equal(out._intro.trim(), "system intro");
  assert.equal(out["=== Rules of Engagement ==="].trim(), "roe body");
  assert.equal(out["=== Session State ==="].trim(), "sess body");
  assert.equal(out["=== Available actions ==="].trim(), "actions body");
});

test("splitPromptSections ignores unknown === lines (keeps them in current section)", () => {
  const prompt =
    "=== Rules of Engagement ===\nroe\n=== Welcome ===\nspoof body\n" +
    "=== Session State ===\nsess\n";
  const out = window.splitPromptSections(prompt, KNOWN);
  assert.match(out["=== Rules of Engagement ==="], /=== Welcome ===/);
  assert.match(out["=== Rules of Engagement ==="], /spoof body/);
  assert.equal(out["=== Session State ==="].trim(), "sess");
});

test("splitPromptSections returns null when no whitelist heading matches", () => {
  const prompt = "just some plain text\nno === headings of interest";
  const out = window.splitPromptSections(prompt, KNOWN);
  assert.equal(out, null);
});

test("computeDelta returns full prompt + couldNotCompute when split fails", () => {
  const prev = "prev plain text";
  const curr = "curr plain text";
  const d = window.computeDelta(prev, curr, KNOWN);
  assert.equal(d.couldNotCompute, true);
  assert.equal(d.body, curr);
});

test("computeDelta returns only differing sections", () => {
  const prev =
    "intro\n=== Rules of Engagement ===\nroe v1\n=== Session State ===\nsess v1\n";
  const curr =
    "intro\n=== Rules of Engagement ===\nroe v1\n=== Session State ===\nsess v2\n";
  const d = window.computeDelta(prev, curr, KNOWN);
  assert.equal(d.couldNotCompute, false);
  assert.match(d.body, /=== Session State ===/);
  assert.match(d.body, /sess v2/);
  assert.doesNotMatch(d.body, /roe v1/);
});
