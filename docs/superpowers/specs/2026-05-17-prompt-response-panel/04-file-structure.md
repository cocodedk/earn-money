# File Structure & Line Budgets

Project rule: **200-line cap per code/test/HTML/CSS/JS file**. Splits below are pre-planned to stay within budget.

## Server (modify)

| File | Today | Change | After |
|------|-------|--------|-------|
| `src/earn_money/agent/hacker_loop.py` | 285 lines | `_on_llm_response` gains `*, system, prompt, attempt, used_response_format`; `_on_action_parsed` gains `*, attempt`; new `_on_action_parse_failed(turn, attempt, error)` hook; `run()` call sites updated | ~305 |
| `src/earn_money/dashboard/probe_runner.py` | 294 lines | Three hook overrides emit new SSE fields/events; signatures match base | ~320 |

**Both files are already over the 200-line cap** (a pre-existing violation, not caused by this change). The additions here are surgical (≤15 lines each) and do not meaningfully worsen the violation. Splitting these two files into focused submodules is **explicit follow-up work** — out of scope for this branch. A separate spec / plan should:

- Extract `_call_provider_with_rf_fallback` and `_SYSTEM_PROMPT` from `hacker_loop.py` into `src/earn_money/agent/llm_call.py`.
- Split `probe_runner.py` into `probe_runner.py` (class + lifecycle) and `probe_runner_helpers.py` (module-level functions: `_augment_with_base_host`, `_apply_max_turns`, `_resolve_model_safely`, `_est_tokens`, `_summarise`).

Both extractions are mechanical; both are unrelated to the prompt-panel feature and would only inflate this change's risk surface.

## Frontend (modify)

All frontend assets live under `src/earn_money/dashboard/templates/`. The `_STATIC` constant in `server.py` resolves to `src/earn_money/dashboard/templates/static/`. Use that as the canonical prefix in commits, tests, and reviews — never the shorter `templates/static/` form.

| File | Today | Change | After |
|------|-------|--------|-------|
| `src/earn_money/dashboard/templates/index.html` | 83 lines | Add `<aside id="probe-detail">` skeleton; wrap timeline + aside in a `.probe-body` grid container; add `<link rel="stylesheet" href="/static/probe-detail.css">` AFTER existing probe/dashboard CSS so panel rules can override base styles; add `<script>` tags for the three new JS files in dependency order (see "Server routes" below) | ~110 |
| `src/earn_money/dashboard/templates/static/probe.css` | 108 lines | Add grid wrapper + responsive collapse | ~140 |
| `src/earn_money/dashboard/templates/static/probe.js` | 84 lines | **No state access at all.** Owns DOM event handlers (timeline clicks, tab toggle, follow-latest button, "start probe" form). At boot: registers an `onChange` callback with `probe-state.js` that triggers a render of both panels; wires the EventSource so each SSE event is forwarded to `window.probeReducer(event)`. On form submit (new probe): fires `probeReducer({stage: "probe_start"})` BEFORE opening the new EventSource. Never reads or writes `state`; never calls render manually after `probeReducer` (the reducer's `onChange` is the sole render trigger) | ~115 |
| `src/earn_money/dashboard/templates/static/probe-render.js` | 84 lines | **Read-only renderer.** Renders the left timeline column from `state.turns`. Calls `window.getTurnStatus()` for badge text. Does NOT mutate state. (All event-handling logic moved out — into `probe-state.js`) | ~100 |

## Frontend (new)

| File | Lines (budget) | Purpose |
|------|----------------|---------|
| `src/earn_money/dashboard/templates/static/probe-status.js` | ≤60 | Pure helpers. `window.getTurnStatus(turn) -> enum` (priority order in `01-architecture.md`) and `window.formatTurnStatus(status) -> string` (fixed lookup table). No DOM, no state mutation |
| `src/earn_money/dashboard/templates/static/probe-state.js` | ≤160 | **State owner.** Exposes `window.probeState`, `window.probeReducer(event)`, `setSelectedTurn(n)`, `setActiveTab(t)`, `setFollowLatest(b)`, `onChange(fn)`. Handles SSE stages: `action_pending` (append attempt, capture system/prompt/raw/model), `action_parsed` / `action_parse_failed` (flip `parseOutcome` by `(turn, attempt)`, set `parseError`), `policy` / `observation` / `complete` (update turn fields), `probe_error` (set `state.runError`), `probe_start` (synthetic — clears all state for a new run). Unknown `stage` values are ignored silently. Calls the registered `onChange` callback once after each mutation. **Only writer to state in the whole app** |
| `src/earn_money/dashboard/templates/static/probe-detail.css` | ≤150 | Right panel layout: header, sub-tabs, attempt cards, warning border, prompt `<pre>` styling |
| `src/earn_money/dashboard/templates/static/probe-detail.js` | ≤170 | Right-panel **read-only renderer**: header builder, tab switcher, delta-diff function (whitelist-based heading split, see `03-right-panel-ux.md`), attempt-card builder. Calls `window.getTurnStatus()`. Does NOT mutate state |

`probe-state.js` and `probe-detail.js` are the substantive new modules. The delta-diff function (`splitPromptSections(prompt, knownHeadings) → { sectionName: body }`, compare two maps, keep only differing sections) is ~30 lines on its own. `probe-status.js` is intentionally tiny.

## Server routes (modify)

`src/earn_money/dashboard/server.py` — `_STATIC_ROUTES` dict gains four entries:

```python
"/static/probe-status.js":  (_STATIC / "probe-status.js",  _JS),
"/static/probe-state.js":   (_STATIC / "probe-state.js",   _JS),
"/static/probe-detail.css": (_STATIC / "probe-detail.css", _CSS),
"/static/probe-detail.js":  (_STATIC / "probe-detail.js",  _JS),
```

(`_STATIC` already resolves to `src/earn_money/dashboard/templates/static/`.) No new HTTP route. No new handler method.

`index.html` adds one `<link>` (CSS) and four `<script>` tags. **The order matters** and is enforced by an automated test (`test_index_html_script_order` — see `05-test-plan.md`):

```html
<!-- existing probe/dashboard CSS comes first -->
<link rel="stylesheet" href="/static/probe.css">
<link rel="stylesheet" href="/static/probe-detail.css">   <!-- NEW: panel rules override base -->

<!-- ...later in the body, after existing scripts... -->
<script src="/static/probe-status.js"></script>   <!-- defines window.getTurnStatus -->
<script src="/static/probe-state.js"></script>    <!-- defines window.probeState, window.probeReducer -->
<script src="/static/probe-render.js"></script>   <!-- reads state, renders timeline -->
<script src="/static/probe-detail.js"></script>   <!-- reads state, renders right panel -->
<script src="/static/probe.js"></script>          <!-- DOM event handlers; calls reducer; triggers renders -->
```

Dependency rationale: `probe-status.js` is consumed by both renderers; `probe-state.js` exposes the reducer; `probe.js` is loaded last so the reducer + renderers are defined before any DOM event handler can fire.

## Tests (modify + new)

| File | Change |
|------|--------|
| `tests/agent/test_hacker_loop.py` | Add `TestPromptHook`, `TestAttemptIdentity`, and `TestProviderHelper` classes — see `05-test-plan.md` |
| `tests/dashboard/test_probe_runner.py` | Add `TestPromptInSseEvent` and `TestAttemptIdentityInSseEvent` classes — see `05-test-plan.md` |
| `tests/dashboard/test_probe_routes.py` | Register the four new static-asset paths (`probe-status.js`, `probe-state.js`, `probe-detail.css`, `probe-detail.js`); smoke-test 200 + Content-Type |
| `tests/dashboard/test_probe_static_assets.py` (**new**) | Three static-file assertions: (1) `probe-detail.js` has no DOM-write sinks (`innerHTML`, `insertAdjacentHTML`, `outerHTML`, `document.write`, `createContextualFragment`); (2) `index.html` references `/static/probe-detail.css`; (3) the five probe JS files appear in dependency order inside `index.html` |
| `tests/frontend/probe_state.test.mjs` (**new**) | Reducer + status-helper tests for the shipped JS. Run via `node --test` (built into Node 18+). Invoked from pytest via a tiny subprocess wrapper that skips with a clear message if `node` is not on PATH (zero new Python deps; one optional system dep). Covers reducer cases enumerated in `05-test-plan.md` plus `getTurnStatus`/`formatTurnStatus`. Tests the actually-shipped JS — no Python mirror to drift |

The static safety + asset tests are the only automated frontend tests for layout/DOM — consistent with the project today. The status helper gets its own dedicated tests because it's shared UI logic with non-trivial priority rules.

## Files NOT touched

- `src/earn_money/agent/probe_actions.py` — parsing logic unchanged
- `src/earn_money/dashboard/templates/static/{tabs.js, render.js, render_panels.js, dashboard.js}` — recon-tab and shared-component code untouched
- `src/earn_money/dashboard/templates/static/{tokens.css, dashboard.css, panels.css}` — global styles untouched
- Any non-dashboard runner, ledger, or recon code

## Total impact

- 2 server files modified (hook signatures + SSE overrides — surgical)
- 4 frontend files modified (including `index.html` CSS link + script-order change; `probe-render.js` shrinks because state mutation moves out)
- 4 frontend files added (`probe-status.js`, `probe-state.js`, `probe-detail.css`, `probe-detail.js`)
- 3 test files modified
- 2 test files added (`test_probe_static_assets.py`, `probe_state.test.mjs` — Node-runnable)
- 1 server route file modified (four-line additions to `_STATIC_ROUTES`)

Net additions: ~500 lines of new frontend code across four files. No new dependencies. No new HTTP routes. Each file is single-purpose and well under 200 lines.
