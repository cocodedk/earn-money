# Frontend tasks (F1–F9)

Test invocation: `node --test tests/frontend/` for fast iter; `node --test --experimental-test-coverage tests/frontend/` for coverage. Node 22+ is present on this dev machine (`node --version` returns `v22.22.x`).

**Frontend shape rule:** plain `<script>` tags, no ES modules, no build step. Helpers/state attach to `window`. Tests use Node's built-in `node:test` and `node:assert/strict`. Each test file imports the production JS by reading the file and `eval`-ing it in a sandbox where `window = globalThis` — see F1 for the harness setup.

---

## F1: `probe-status.js` + JS test infrastructure

**Files:**
- Create: `src/earn_money/dashboard/templates/static/probe-status.js`
- Create: `tests/frontend/_load.mjs` — shared harness for loading prod JS into a test scope
- Create: `tests/frontend/probe_status.test.mjs`
- Create: `tests/frontend/test_probe_state_runner.py` — pytest wrapper that runs `node --test` (skips if node missing)

- [ ] **Step 1: Write the harness `tests/frontend/_load.mjs`.**

```js
// tests/frontend/_load.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const STATIC = resolve(here, "..", "..", "src", "earn_money", "dashboard", "templates", "static");

export function loadProdScript(filename) {
  // Production JS attaches to `window`. In tests, alias globalThis.
  globalThis.window = globalThis;
  const src = readFileSync(resolve(STATIC, filename), "utf8");
  (0, eval)(src);   // indirect eval — runs in global scope
}
```

- [ ] **Step 2: Write failing tests `tests/frontend/probe_status.test.mjs`.**

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadProdScript } from "./_load.js";

loadProdScript("probe-status.js");

test("null turn → in_progress", () => {
  assert.equal(window.getTurnStatus(null), "in_progress");
});

test("pending attempt + not complete → in_progress", () => {
  const t = { attempts: [{ parseOutcome: "pending" }], complete: false };
  assert.equal(window.getTurnStatus(t), "in_progress");
});

test("single ok attempt + complete → ok", () => {
  const t = { attempts: [{ parseOutcome: "ok" }], complete: true };
  assert.equal(window.getTurnStatus(t), "ok");
});

test("failed then ok → recovered", () => {
  const t = { attempts: [{ parseOutcome: "failed" }, { parseOutcome: "ok" }], complete: true };
  assert.equal(window.getTurnStatus(t), "recovered");
});

test("all failed → parse_failed", () => {
  const t = { attempts: [{ parseOutcome: "failed" }, { parseOutcome: "failed" }], complete: true };
  assert.equal(window.getTurnStatus(t), "parse_failed");
});

test("ok + policy denied → policy_blocked (beats ok)", () => {
  const t = {
    attempts: [{ parseOutcome: "ok" }],
    policyDecision: { allowed: false },
    complete: true,
  };
  assert.equal(window.getTurnStatus(t), "policy_blocked");
});

test("recovered + policy denied → policy_blocked (beats recovered)", () => {
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
```

- [ ] **Step 3: Run.** `node --test tests/frontend/probe_status.test.mjs` — fails: no `probe-status.js`.
- [ ] **Step 4: Create the production file.**

```js
// src/earn_money/dashboard/templates/static/probe-status.js
window.getTurnStatus = function getTurnStatus(turn) {
  if (!turn) return "in_progress";
  if (turn.policyDecision && turn.policyDecision.allowed === false) {
    return "policy_blocked";
  }
  const attempts = turn.attempts || [];
  const hasOk      = attempts.some(a => a.parseOutcome === "ok");
  const hasFailed  = attempts.some(a => a.parseOutcome === "failed");
  const hasPending = attempts.some(a => a.parseOutcome === "pending");
  if (hasPending && !turn.complete) return "in_progress";
  if (hasOk && hasFailed)           return "recovered";
  if (hasOk)                        return "ok";
  if (hasFailed)                    return "parse_failed";
  return "in_progress";
};

window.formatTurnStatus = function formatTurnStatus(status) {
  return ({
    "ok":             "ok",
    "recovered":      "invalid_action → recovered",
    "parse_failed":   "parse_failed",
    "policy_blocked": "policy_blocked",
    "in_progress":    "in_progress",
  })[status] || status;
};
```

- [ ] **Step 5: Write the pytest wrapper `tests/frontend/test_probe_state_runner.py`.**

```python
import shutil, subprocess
import pytest

def test_frontend_js_suite():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH — install Node 18+ to run the JS test suite")
    result = subprocess.run(
        [node, "--test", "tests/frontend/"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
```

- [ ] **Step 6: Run.** Both `node --test tests/frontend/` and `uv run pytest tests/frontend/` pass.
- [ ] **Step 7: Commit.** `feat(probe-panel): probe-status.js + JS test harness`
- [ ] **Step 8: `/simplify`.**

---

## F2: `probe-state.js` reducer + comprehensive tests

**Files:**
- Create: `src/earn_money/dashboard/templates/static/probe-state.js`
- Create: `tests/frontend/probe_state.test.mjs`

- [ ] **Step 1: Write failing tests `tests/frontend/probe_state.test.mjs`.**

Use the harness. The reducer needs to expose `window.probeState`, `window.probeReducer(event)`, `setSelectedTurn`, `setActiveTab`, `setFollowLatest`, `onChange(fn)`. Each test calls `_reset()` (a helper that wipes state) before running.

```js
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { loadProdScript } from "./_load.js";

loadProdScript("probe-status.js");
loadProdScript("probe-state.js");

function reset() {
  window.probeReducer({ stage: "probe_start" });
}
beforeEach(reset);

const evt = (stage, data) => ({ stage, ...data });

test("action_pending appends pending attempt", () => {
  window.probeReducer(evt("action_pending", {
    turn: 1, attempt: 1, used_response_format: true,
    system: "s", prompt: "p", raw: "r", model: "m",
  }));
  const t = window.probeState.turns[1];
  assert.equal(t.attempts.length, 1);
  assert.equal(t.attempts[0].parseOutcome, "pending");
  assert.equal(t.attempts[0].attempt, 1);
  assert.equal(t.system, "s");
  assert.equal(t.prompt, "p");
});

test("action_parse_failed flips matching attempt to failed", () => {
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "{", model: "m" }));
  window.probeReducer(evt("action_parse_failed", { turn: 1, attempt: 1, error: "boom" }));
  const a = window.probeState.turns[1].attempts[0];
  assert.equal(a.parseOutcome, "failed");
  assert.equal(a.parseError, "boom");
  assert.equal(window.probeState.turns[1].attempts.length, 1);
});

test("second action_pending appends attempt 2 without touching attempt 1", () => {
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "{", model: "m" }));
  window.probeReducer(evt("action_parse_failed", { turn: 1, attempt: 1, error: "boom" }));
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 2, used_response_format: false, system: "s", prompt: "p", raw: "ok", model: "m" }));
  const t = window.probeState.turns[1];
  assert.equal(t.attempts.length, 2);
  assert.equal(t.attempts[0].parseOutcome, "failed");
  assert.equal(t.attempts[1].parseOutcome, "pending");
});

test("action_parsed flips only the matching attempt to ok", () => {
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "{", model: "m" }));
  window.probeReducer(evt("action_parse_failed", { turn: 1, attempt: 1, error: "boom" }));
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 2, used_response_format: false, system: "s", prompt: "p", raw: "ok", model: "m" }));
  window.probeReducer(evt("action_parsed", { turn: 1, attempt: 2, action: {}, parse_recovered: true }));
  const t = window.probeState.turns[1];
  assert.equal(t.attempts[0].parseOutcome, "failed");
  assert.equal(t.attempts[1].parseOutcome, "ok");
  assert.equal(window.getTurnStatus(t), "recovered");
});

test("setSelectedTurn disables followLatest", () => {
  window.setSelectedTurn(2);
  assert.equal(window.probeState.selectedTurn, 2);
  assert.equal(window.probeState.followLatest, false);
});

test("after manual select, new turn does NOT change selectedTurn", () => {
  window.setSelectedTurn(2);
  window.probeReducer(evt("action_pending", { turn: 3, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "", model: "m" }));
  assert.equal(window.probeState.selectedTurn, 2);
});

test("setFollowLatest(true) jumps to latest turn", () => {
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "", model: "m" }));
  window.probeReducer(evt("action_pending", { turn: 2, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "", model: "m" }));
  window.setSelectedTurn(1);
  window.setFollowLatest(true);
  assert.equal(window.probeState.selectedTurn, 2);
});

test("probe_error sets runError without touching turns", () => {
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "", model: "m" }));
  window.probeReducer({ stage: "probe_error", message: "boom" });
  assert.equal(window.probeState.runError, "boom");
  assert.ok(window.probeState.turns[1]);
});

test("probe_start clears all state", () => {
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "", model: "m" }));
  window.setSelectedTurn(1);
  window.probeReducer({ stage: "probe_start" });
  assert.deepEqual(window.probeState.turns, {});
  assert.equal(window.probeState.selectedTurn, null);
  assert.equal(window.probeState.followLatest, true);
  assert.equal(window.probeState.runError, null);
});

test("unknown stage is ignored silently", () => {
  const before = JSON.stringify(window.probeState);
  window.probeReducer({ stage: "totally_unknown" });
  assert.equal(JSON.stringify(window.probeState), before);
});

test("onChange fires exactly once per accepted event", () => {
  let count = 0;
  window.onChange(() => count++);
  window.probeReducer(evt("action_pending", { turn: 1, attempt: 1, used_response_format: true, system: "s", prompt: "p", raw: "", model: "m" }));
  assert.equal(count, 1);
  window.probeReducer({ stage: "totally_unknown" });
  assert.equal(count, 1); // unknown stage = no fire
});
```

- [ ] **Step 2: Run.** Fails: no `probe-state.js`.
- [ ] **Step 3: Implement `probe-state.js`.** Single object owning state; one `_apply` per event stage; `_notify()` called only when state actually changed. Keep under 160 lines. See architecture spec for invariants.

- [ ] **Step 4: Run.** All tests pass.
- [ ] **Step 5: Commit.** `feat(probe-panel): probe-state.js reducer + lifecycle helpers`
- [ ] **Step 6: `/simplify`.**

---

## F3: `probe-detail.css`

**Files:** Create `src/earn_money/dashboard/templates/static/probe-detail.css` (≤150 lines).

No automated tests (visual). Must include `.probe-body { display: grid; grid-template-columns: minmax(360px, 2fr) minmax(480px, 3fr); ... }` and styles for attempt cards (default + warning borders).

- [ ] Implement, then visually sanity-check in browser (B7-style smoke).
- [ ] Commit. `feat(probe-panel): probe-detail.css layout + styling`
- [ ] `/simplify`.

---

## F4: `probe-detail.js` renderer

**Files:**
- Create: `src/earn_money/dashboard/templates/static/probe-detail.js`
- (Tests for `splitPromptSections` could live in `probe_state.test.mjs` — add one test per spec case: known heading split, unknown `===` line stays in current section, fallback when no matches.)

Implementation order:
1. `splitPromptSections(prompt, knownHeadings)` — pure function.
2. `renderHeader(state)` — calls `getTurnStatus` + `formatTurnStatus`.
3. `renderPromptSection(turn, mode)` — Delta vs Full.
4. `renderAttemptCards(turn)` — one card per attempt.
5. `renderDetailPanel()` — top-level; registered as `onChange` listener by `probe.js`.

All LLM-controlled fields go through `textContent`. No `innerHTML` anywhere — the static-asset regex test (F9) blocks that on commit.

- [ ] Run JS tests + commit + `/simplify`.

---

## F5: Refactor `probe-render.js` to read-only

**Files:** Modify `src/earn_money/dashboard/templates/static/probe-render.js`. Remove every state mutation; rely on `window.probeState` populated by `probe-state.js`. Calls `window.getTurnStatus()` + `window.formatTurnStatus()` for badge.

- [ ] Add a JS test confirming `probe-render.js` does not assign to any `window.probeState.*` field (regex check or runtime spy).
- [ ] Commit. `refactor(probe-panel): probe-render.js becomes read-only renderer`
- [ ] `/simplify`.

---

## F6: Refactor `probe.js` to no-state dispatcher

**Files:** Modify `src/earn_money/dashboard/templates/static/probe.js`.

Boot sequence:
```js
window.onChange(() => { window.renderTimeline(); window.renderDetailPanel(); });
// New-probe form submit:
form.addEventListener("submit", () => {
  window.probeReducer({ stage: "probe_start" });
  // ... then POST /api/probe/start, then open EventSource
});
// EventSource onmessage forwards event.data to probeReducer.
```

Strict: `probe.js` never reads or writes `window.probeState`.

- [ ] Commit. `refactor(probe-panel): probe.js becomes no-state dispatcher`
- [ ] `/simplify`.

---

## F7: `index.html` wiring

**Files:** Modify `src/earn_money/dashboard/templates/index.html`.

- [ ] Add `<aside id="probe-detail">` skeleton, wrap timeline + aside in `.probe-body` grid container.
- [ ] Add `<link rel="stylesheet" href="/static/probe-detail.css">` AFTER existing `<link>` for `probe.css`.
- [ ] Add `<script>` tags in dependency order:
  ```html
  <script src="/static/probe-status.js"></script>
  <script src="/static/probe-state.js"></script>
  <script src="/static/probe-render.js"></script>
  <script src="/static/probe-detail.js"></script>
  <script src="/static/probe.js"></script>
  ```
- [ ] Commit. `chore(probe-panel): wire new assets in index.html`
- [ ] `/simplify`.

---

## F8: Register four new static routes

**Files:** Modify `src/earn_money/dashboard/server.py` (`_STATIC_ROUTES`); modify `tests/dashboard/test_probe_routes.py` (add four route smoke tests).

- [ ] Write failing route tests (404 → 200 + correct Content-Type).
- [ ] Add four entries to `_STATIC_ROUTES` per `04-file-structure.md § Server routes`.
- [ ] Run. Pass.
- [ ] Commit. `feat(probe-panel): register four new static routes`
- [ ] `/simplify`.

---

## F9: Static-asset safety + structure tests

**Files:** Create `tests/dashboard/test_probe_static_assets.py` with the three regex assertions (no DOM-write sinks; CSS link present; script order).

- [ ] Tests already fully specified in `consolidated.v6.md § test_probe_static_assets.py` — copy verbatim.
- [ ] Run. Pass (everything from F1–F7 should already satisfy these).
- [ ] Commit. `test(probe-panel): static-asset safety + structure regression tests`
- [ ] `/simplify`.

---

**Frontend complete.** Continue with `03-coverage-and-e2e.md`.
