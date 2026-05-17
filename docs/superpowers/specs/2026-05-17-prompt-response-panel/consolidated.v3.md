# Prompt & Response Detail Panel — Consolidated Spec

**Version:** v3
**Source folder:** `docs/superpowers/specs/2026-05-17-prompt-response-panel/`
**Consolidated:** 2026-05-17
**Supersedes:** `consolidated.v2.md` (kept for diff reference)

## Changes from v2 (addressing review round 2)

All five round-2 findings adopted. No push-back this round.

| # | Reviewer finding | v2 → v3 change |
|---|------------------|----------------|
| 1 | `getTurnStatus()` script-order risk | **Adopted, reviewer's preferred option.** New `src/earn_money/dashboard/templates/static/probe-status.js` exposes `window.getTurnStatus`; loaded before `probe-render.js` and `probe-detail.js`. Timeline no longer depends on a detail-panel module |
| 2 | "Prompts ride multiple events" wording was wrong | **Fixed.** Single-source-of-truth paragraph now correctly says: prompts/system/raw ride only on `action_pending`; parse-result events carry only attempt identity + outcome |
| 3 | Attempt state missing `parseError` | **Added.** State shape gains `parseError: string \| null`; right-panel UX section documents the source (from `action_parse_failed.error`) |
| 4 | `_last_used_response_format` brittle | **Added implementation rule.** `_get_llm_response` should return `(raw, used_response_format)` tuple; caller passes `used_response_format` directly into the hook — do not route through instance state |
| 5 | Innerhtml grep test catches comments | **Documented.** Author note in test plan: don't mention forbidden DOM APIs in `probe-detail.js` comments either; intentional strictness |

## Round 1→2→3 history

- **v1** (committed `c0b4c1f`): initial spec; review flagged blockers around event attempt identity.
- **v2**: 10 findings addressed — 7 adopted in full, 2 partially with push-back, 1 acknowledged-with-pushback-on-fix. Reviewer called the result "implementable" subject to 5 small edits.
- **v3** (this file): all 5 round-2 edits applied. Reviewer's verdict: "I would approve v2 after these small edits." → v3 should pass.

## Files included (in order)

1. `00-overview.md`
2. `01-architecture.md`
3. `02-sse-event-shape.md`
4. `03-right-panel-ux.md`
5. `04-file-structure.md`
6. `05-test-plan.md`
7. `06-non-goals.md`

Each source file is wrapped with `BEGIN <filename>` / `END <filename>` HTML-comment markers.

---

<!-- ============================================================ -->
<!-- BEGIN 00-overview.md -->
<!-- ============================================================ -->

# Prompt & Response Detail Panel — Overview

## Goal

Surface the **full prompt sent to the LLM** and the **full raw response received**, per turn, on the Probe Live Tab. Today the timeline shows only a 200-character `raw_excerpt`; the prompt is invisible. This change makes the LLM exchange fully observable for debugging model behaviour (e.g. the qwen `response_format` garbage retries we hit on 2026-05-17).

## Why

The retry-without-`response_format` fix landed in commits `5627d5c` → `584dc20`. On the live VPS dashboard the operator can now see turns succeed after a silent retry — but cannot see *what the model actually received* or *what it actually returned*. Two concrete debugging tasks that are currently impossible:

1. **Diagnose model quirks.** Confirm "qwen returns garbage with `response_format` on" requires reading the prompt the model saw (was `response_format` actually passed? what did the system prompt look like?) and the full response (is it always JSON-fence-stripped half-output, or random tokens?). The 200-char excerpt is too short.
2. **Validate scope is in the prompt.** When the operator changed RoE handling for `local_lab` (commit `8e4f184`), they had no way to confirm the LLM was actually shown the augmented `allowed_hosts`. Reading the prompt directly answers this.

## Scope

In scope:
- New right-side detail panel in the Probe tab, side-by-side with the existing timeline.
- SSE event carries full `prompt` and full `raw` per LLM call (both attempts when retry-without-`response_format` fires).
- Two sub-tabs in the panel: **Delta** (per-turn changes only) and **Full** (verbatim prompt).
- Retry attempts shown stacked, labelled, with warning/default styling (icon + border, not color-alone — accessibility).

Out of scope:
- Persisting prompts/responses across page reloads. The transcript lives in browser memory for the run; refreshing the page loses it.
- Per-program prompt history across runs. One run, one transcript.
- Server-side prompt diffing or storage — diff is computed in the browser.
- Cost/token accounting beyond the existing per-turn `estimated_tokens`.

See `06-non-goals.md` for the full exclusion list.

## Acceptance Criteria

Implementation is done when all of these hold:

1. **Every parse outcome carries an attempt identity.** `turn/action_parsed` events include `attempt`; first-attempt parse failures emit a new `turn/action_parse_failed` event carrying `{turn, attempt, error}`. The UI never infers attempt identity from event ordering.
2. **`used_response_format` reflects the actual provider call.** Whatever the helper returned — not a value derived from attempt number. A test covers the case where attempt 1 itself runs without `response_format`.
3. **System prompt is visible.** The SSE event carries `system` and `prompt` as separate fields, matching how `provider.complete()` is invoked.
4. **Header status comes from one helper.** A single `window.getTurnStatus(turnState)` function in its own shared `probe-status.js` file produces the badge text; both timeline and detail panel call it. `index.html` loads `probe-status.js` before the two renderer files so the global is defined when either calls it.
5. **Prompt rendered once per turn.** Attempt cards show only per-attempt metadata + response + parse status. Prompt is NOT duplicated across attempt cards (the retry uses the same prompt — duplication is pure noise).
6. **`probe-detail.js` has no `innerHTML` or `insertAdjacentHTML`.** Enforced by an automated test, not just a manual grep.
7. **`raw` and `prompt` are never truncated at the server.** The UI renders them in a scrollable `<pre>`. Size warnings (if any) are deferred to a future revision.

## References

- [`01-architecture.md`](01-architecture.md) — server + client overview
- [`02-sse-event-shape.md`](02-sse-event-shape.md) — wire format
- [`03-right-panel-ux.md`](03-right-panel-ux.md) — layout, tabs, retry stacking
- [`04-file-structure.md`](04-file-structure.md) — files to create/modify, line budgets
- [`05-test-plan.md`](05-test-plan.md) — tests and manual verification
- [`06-non-goals.md`](06-non-goals.md) — explicit exclusions

<!-- ============================================================ -->
<!-- END 00-overview.md -->
<!-- ============================================================ -->

---

<!-- ============================================================ -->
<!-- BEGIN 01-architecture.md -->
<!-- ============================================================ -->

# Architecture

The change is **purely additive**. No protocol breakage, no new server route, no per-run state cache.

## Server-side

Three hook signatures change. The new fields are derived from values already in scope at each call site — no new state, no new helpers in `hacker_loop.py`.

### `_on_llm_response` (signature change)

Today:
```python
def _on_llm_response(self, turn: int, raw: str | None, model_id: str | None) -> None: ...
```

New:
```python
def _on_llm_response(
    self,
    turn: int,
    raw: str | None,
    model_id: str | None,
    *,
    system: str,                   # system prompt passed as provider.complete(system=...)
    prompt: str,                   # user prompt passed as provider.complete(user=...)
    attempt: int,                  # call ordinal within this turn (1, 2, ...)
    used_response_format: bool,    # what THIS call actually sent — read from helper return value
) -> None: ...
```

`system` is `_SYSTEM_PROMPT` (module constant, same value every call). `prompt` is the result of `_build_prompt()` for the turn. `attempt` is `1` on the first call, `2` on the retry. `used_response_format` is the value the helper returned from this specific call — NOT derived from attempt number.

**Implementation rule (avoids a subtle future bug):** `_get_llm_response` should return `(raw, used_response_format)` as a tuple and the caller in `run()` should pass `used_response_format` directly into the hook call — do not route through `self._last_used_response_format`. Routing through instance state works today, but a future change that adds any other provider call between the helper return and the hook invocation will silently clobber `_last_used_response_format` and the dashboard will show wrong data. Returning the tuple makes the pairing structural, not temporal.

### `_on_action_parsed` (signature change)

Today:
```python
def _on_action_parsed(self, turn: int, action: Any, parse_recovered: bool) -> None: ...
```

New:
```python
def _on_action_parsed(
    self,
    turn: int,
    action: Any,
    parse_recovered: bool,
    *,
    attempt: int,                  # which call's response actually parsed
) -> None: ...
```

This is the blocker fix: the browser can no longer guess which attempt produced the parsed action.

### `_on_action_parse_failed` (new hook)

```python
def _on_action_parse_failed(
    self,
    turn: int,
    attempt: int,
    error: str,
) -> None: ...
```

Called from inside the `except ActionParseError` block in `run()`. Fires for every failed parse attempt — once if no retry runs, twice if both attempts fail.

### `ProbeRunner` overrides

All three hooks are overridden in `ProbeRunner` to emit SSE events. Signatures match the base class. No new HTTP route.

### Single source of truth

Prompts ride the existing `/api/probe/stream` SSE channel **on `turn/action_pending` events only** (that's where `system`, `prompt`, and `raw` live). The new `turn/action_parsed` and `turn/action_parse_failed` events carry only attempt identity + parse outcome — they do not re-send the prompt. Server keeps no per-run prompt cache; once an event is sent, the data is the browser's responsibility.

## Client-side

The Probe tab becomes a 2-column CSS grid:

```
┌─────────────────┬──────────────────────────┐
│  TIMELINE       │  DETAIL PANEL            │
│  (~40%)         │  (~60%)                  │
│                 │                          │
│  ▸ TURN 1 ✓     │  TURN 2 · qwen…          │
│  ▸ TURN 2 ✗→✓   │  ┌─────┬────┐            │
│  ▸ TURN 3 …     │  │Delta│Full│            │
│                 │  └─────┴────┘            │
│                 │  #1 with response_format │
│                 │  ⚠ "encoding=UTF-8"      │
│                 │  #2 without              │
│                 │  ✓ {"tool":"get"…}       │
└─────────────────┴──────────────────────────┘
```

The left column is the existing timeline, unchanged in rendering logic — it just lives inside a grid cell now. The right column is a new `<aside>` populated by a new render module.

### Client-side state shape

```js
state.turns = {
  1: {
    system,                       // captured once per turn from first action_pending
    prompt,                       // captured once per turn from first action_pending
    attempts: [
      { attempt, raw, model, used_response_format, ts, parseOutcome, parseError }
      // parseOutcome: "pending" | "ok" | "failed" — set from action_parsed / action_parse_failed
      // parseError:   string | null — populated from action_parse_failed.error; null on "ok" / "pending"
    ],
    policyDecision: {...},
    observation: {...},
    complete: true,
  },
  2: { attempts: [...], ... },
};
state.selectedTurn = 2;        // null until first click → auto-follow latest
state.followLatest = true;     // becomes false after first manual click
state.activeTab = "delta";     // "delta" | "full", persists across turn changes
```

Each `turn/action_pending` event appends an attempt entry (with `parseOutcome="pending"`). The matching `turn/action_parsed` or `turn/action_parse_failed` event finds the entry by `(turn, attempt)` and flips `parseOutcome` to `"ok"` or `"failed"` — never inferred from ordering.

The right panel re-renders when `selectedTurn`, `activeTab`, or any field on the selected turn changes.

### Status derivation

A single helper lives in its own tiny shared file, `probe-status.js`:

```js
// src/earn_money/dashboard/templates/static/probe-status.js
window.getTurnStatus = function getTurnStatus(turnState) {
  // Returns: "in_progress" | "ok" | "recovered" | "parse_failed" | "policy_blocked" | "error"
  // Derived from attempts[].parseOutcome, policyDecision, observation, complete.
};
```

**Loading rule:** `index.html` loads `probe-status.js` BEFORE both `probe-render.js` (timeline) and `probe-detail.js` (right panel). The dashboard JS is plain `<script>` tags (not ES modules), so the helper is exposed on `window` and load order is the contract. Putting it in a dedicated file (not `probe-detail.js`) avoids the timeline depending on a detail-panel module.

Both the timeline summary (left column) and the detail header (right column) call `window.getTurnStatus()`. The header text ("invalid_action → recovered", etc.) is built from this single source. No status enum is stored on `state.turns[N]` — always derived.

## Boundary discipline

- **Status helper** (`probe-status.js`) — pure function over `turnState`. No DOM access. No state mutation. Loaded first.
- **Timeline renderer** (`probe-render.js`) — owns left-column rendering. Reads `state.turns` only for "which turns exist + summary". Calls `window.getTurnStatus()` for badge text.
- **Detail panel renderer** (`probe-detail.js`) — owns right-column rendering. Reads `state.turns[selectedTurn]` only. Calls `window.getTurnStatus()` for header text.
- **Probe dispatcher** (`probe.js`) — owns selection + tab state. Re-emits change events for both renderers.

The two renderers do not call each other. `probe-status.js` is the only shared logic.

<!-- ============================================================ -->
<!-- END 01-architecture.md -->
<!-- ============================================================ -->

---

<!-- ============================================================ -->
<!-- BEGIN 02-sse-event-shape.md -->
<!-- ============================================================ -->

# SSE Event Shape

Three event shapes change:

1. `turn/action_pending` — gains new fields (prompt, system, raw, attempt, used_response_format)
2. `turn/action_parsed` — gains `attempt`
3. `turn/action_parse_failed` — **new event**, fires on every failed parse

Other event types (`turn/policy`, `turn/observation`, `turn/complete`, `finding`, `done`, `probe_error`, `_keepalive`) are unchanged.

## `turn/action_pending`

### Today

```json
{
  "event": "turn",
  "data": {
    "turn": 2,
    "stage": "action_pending",
    "model": "qwen/qwen3-235b-a22b",
    "raw_excerpt": "{",
    "estimated_tokens": 0
  }
}
```

### New

```json
{
  "event": "turn",
  "data": {
    "turn": 2,
    "stage": "action_pending",
    "model": "qwen/qwen3-235b-a22b",
    "attempt": 1,
    "used_response_format": true,
    "system": "You are assisting with authorized security testing.\n…",
    "prompt": "=== Rules of Engagement ===\n…",
    "raw": "{",
    "raw_excerpt": "{",
    "estimated_tokens": 0
  }
}
```

### Field semantics

| Field | Type | Notes |
|-------|------|-------|
| `attempt` | int | Call ordinal within this turn, 1-indexed. In current code reaches at most 2 (retry-without-`response_format`); field is open-ended for future expansion |
| `used_response_format` | bool | What THIS specific call actually sent to the provider. Read from the helper's return value; never derived from `attempt`. An `attempt=1` event can carry `false` if the caller started with `with_response_format=false` (e.g., a future model-capability gate) |
| `system` | string | The exact `system=…` kwarg passed to `provider.complete()`. In current code this is the `_SYSTEM_PROMPT` module constant — same value every call. Emitted per-event for self-containment |
| `prompt` | string | The exact `user=…` kwarg passed to `provider.complete()`. Built by `_build_prompt()` — contains RoE + session view + action menu. **Does NOT include the system prompt** (that's the `system` field) |
| `raw` | string | Full untruncated raw LLM response. May be empty string if provider returned `None`/empty |
| `raw_excerpt` | string | **Kept for back-compat.** Still `raw[:200]` so the timeline renderer doesn't need changes |

**What's NOT in the payload (deliberately, for v1):** `temperature`, `max_tokens`, `response_format_type`, or any other provider kwargs. The current debugging goal only requires "did response_format go out, yes/no?" and the operator gets that from `used_response_format`. Broader request metadata is deferred until a concrete debugging need motivates it.

## `turn/action_parsed`

### Today

```json
{
  "event": "turn",
  "data": {
    "turn": 1,
    "stage": "action_parsed",
    "action": {"tool": "get", "category": "http_get", "args": {...}},
    "parse_recovered": false
  }
}
```

### New

```json
{
  "event": "turn",
  "data": {
    "turn": 1,
    "stage": "action_parsed",
    "attempt": 2,
    "action": {"tool": "get", "category": "http_get", "args": {...}},
    "parse_recovered": true
  }
}
```

`attempt` identifies which `action_pending` event's raw text actually parsed. The browser must NOT infer this from event ordering.

## `turn/action_parse_failed` (new)

Fires from inside the `except ActionParseError` block in `HackerLoop.run()`. One event per failed parse attempt.

```json
{
  "event": "turn",
  "data": {
    "turn": 1,
    "stage": "action_parse_failed",
    "attempt": 1,
    "error": "Expecting value: line 1 column 2 (char 1)"
  }
}
```

The frontend matches this event to the right attempt card via `(turn, attempt)` and flips its `parseOutcome` to `"failed"`.

### Retry case (the common qwen path)

A single turn with a parse-retry produces **four** events in order:

1. `action_pending` `attempt=1, used_response_format=true, raw="{"` (or whatever garbage)
2. `action_parse_failed` `attempt=1, error="..."`
3. `action_pending` `attempt=2, used_response_format=false, raw='{"tool":"get",…}'`
4. `action_parsed` `attempt=2, parse_recovered=true`

All four carry the same `turn` number. Happy path produces only events 1 and 4 (no failure event, `parse_recovered=false`).

### Size budget

- Typical `system`: 1–2 KB (constant)
- Typical `prompt`: 4–8 KB
- Typical `raw`: 80–200 bytes (it's one JSON action)
- Per `action_pending` event: ~6–11 KB
- Worst case per turn (assuming retry): 2 × 11 KB = ~22 KB

**Caveat — large-raw outliers.** A misbehaving model can emit much larger `raw` (thousands of tokens of garbage instead of one JSON object). The 22-KB number is "typical retry," not "worst case." Server makes no attempt to cap; values >100 KB stay full-fidelity over the wire. Soft policy:

- Server never truncates `prompt`, `system`, or `raw` — observability is the whole point of this feature.
- Client renders these in scrollable `<pre>` blocks; browser memory comfortably holds tens of MB.
- If a real-world run produces a `raw` so large it degrades the SSE stream or UI, that's a future-revision problem — add a "this field is 250 KB, click to expand" affordance, NOT a hard truncation.

### Security

All five LLM-controlled string fields (`system`, `prompt`, `raw`, `raw_excerpt`, `model`) MUST be rendered via `textContent` in the browser — never `innerHTML`, never `insertAdjacentHTML`. The `system` prompt itself comes from a project constant, but `prompt` and `raw` contain target-supplied bytes (HTTP response bodies echoed in observations). Display-only rendering with `textContent` is the project convention (see existing `probe-render.js`) and is non-negotiable here. An automated test enforces this for `probe-detail.js` — see `05-test-plan.md`.

### Back-compat

The existing `raw_excerpt` and `estimated_tokens` fields are unchanged. An older browser tab connected to the new server receives extra fields and ignores them. A newer browser connected to an older server (no `attempt` on `action_parsed`, no `action_parse_failed` event) cannot correctly attribute parse status — the detail panel will show all attempts as `"pending"`. Acceptable degradation; both sides ship together.

<!-- ============================================================ -->
<!-- END 02-sse-event-shape.md -->
<!-- ============================================================ -->

---

<!-- ============================================================ -->
<!-- BEGIN 03-right-panel-ux.md -->
<!-- ============================================================ -->

# Right Panel UX

## Layout

The Probe tab body becomes a CSS grid:

```
.probe-body {
  display: grid;
  grid-template-columns: minmax(360px, 2fr) minmax(480px, 3fr);
  gap: 12px;
  min-height: 0;          /* allow children to scroll independently */
}
```

Left cell is the existing timeline `<section>` (no markup changes). Right cell is a new `<aside id="probe-detail">`.

On viewports narrower than ~960px, the grid collapses to a single column; the detail panel moves below the timeline. (Mobile is not a primary use case — the dashboard runs on the operator's laptop and the VPS — but a graceful collapse prevents broken layouts.)

## Header

Always visible at the top of the panel:

```
TURN 2 · qwen/qwen3-235b-a22b · invalid_action → recovered
```

Fields:
- Turn number from the selected turn
- Model from the most recent attempt
- Status text derived by calling `window.getTurnStatus(state.turns[N])` — the single shared helper in `probe-status.js` (see `01-architecture.md` for the loading rule). Possible values: `"in_progress"`, `"ok"`, `"recovered"`, `"parse_failed"`, `"policy_blocked"`, `"error"`. The status enum maps to display text (e.g. `"recovered"` → `"invalid_action → recovered"`); both timeline and detail panel call the same helper so they can never disagree.
- Retry indicator (`↻ retried` badge) if `attempts.length > 1`

If no turn is selected (initial state, no events yet), header shows `"Waiting for first turn…"` and tabs are disabled.

## Sub-tabs

Two buttons: **Delta** (default) and **Full**. Selecting a tab persists across turn changes — clicking turn 5 while on the Full tab keeps Full active.

### Delta tab

Splits both the previous turn's prompt and the current turn's prompt on `\n=== ` boundaries. The result is a list of sections (system intro, `=== Rules of Engagement ===`, `=== Session State ===`, `=== Available actions ===`). For each section name, if the bodies differ, render the **current** turn's section. If they're identical, omit.

In practice this is always just the Session State block — RoE doesn't change mid-run, action menu is constant, system prompt is constant. The Delta tab is therefore a tight, scrollable "what's new this turn" view.

If the selected turn is turn 1, Delta shows the entire prompt (no previous turn to diff against) with a small label "first turn — no delta".

### Full tab

Renders the prompt verbatim in a `<pre>` block with monospace font, soft-wrap on, scrollable. No syntax highlighting.

## Panel body — two sections

The panel body has **two stacked sections**:

### 1. Prompt section (rendered ONCE per turn)

The Delta/Full tab toggle controls what shows here. This section displays the `prompt` (and on the Full tab, also `system`) for the selected turn — **not** per-attempt. In current code the retry sends the exact same `user=prompt` kwarg, so duplicating the multi-KB prompt across attempt cards would just make the panel longer to scroll without adding information.

(If a future code change makes the second attempt send a different prompt — which would be a non-trivial design change — the spec at that point should specify how to show the diff. For v1 the prompt is always shared across all attempts in a turn.)

### 2. Attempts section (one card per attempt)

```
┌─ Attempt #1 · with response_format ─────────────────┐
│ Response:                                            │
│ "{"                                                  │
│ ⚠ parse failed: Expecting value: line 1 column 2    │
└──────────────────────────────────────────────────────┘
┌─ Attempt #2 · without response_format ──────────────┐
│ Response:                                            │
│ {"tool":"get","category":"http_get","args":{…}}      │
│ ✓ parsed                                             │
└──────────────────────────────────────────────────────┘
```

Each card shows:
- Header chip: `Attempt #N · with response_format` or `· without response_format` (from `used_response_format`)
- Response body in a scrollable `<pre>` (LLM-controlled, rendered via `textContent`)
- Status row: `✓ parsed` (with default border + check icon) or `⚠ parse failed: <error>` (with warning border + warning icon)

Status comes from `attempts[i].parseOutcome`, which the dispatcher sets when `turn/action_parsed` (`"ok"`) or `turn/action_parse_failed` (`"failed"`) arrives — matched by `(turn, attempt)`, never inferred from event order. The error string in `⚠ parse failed: <error>` comes from `attempts[i].parseError`, populated from the `action_parse_failed.error` field; it is `null` for `"ok"` and `"pending"` attempts.

Styling: warning attempts use `border-color: var(--color-warning)` AND a `⚠` glyph in the status row. Successful attempts use the default border AND a `✓` glyph. The two are distinguishable without color — accessibility requirement, not optional.

## Selection & follow-latest

- `state.selectedTurn = null` and `state.followLatest = true` initially.
- Each incoming turn-event re-computes the "latest turn" and, if `followLatest`, re-selects it.
- Clicking a turn block in the timeline sets `state.selectedTurn` and `state.followLatest = false`.
- A small button in the panel header `↓ follow latest` reappears whenever `followLatest === false`; clicking it sets `followLatest = true` and selects the latest.

This matches the standard pattern from streaming-log viewers: follow until the user takes manual control.

## Persistence

- Transcript stays visible after the `done` event.
- The next `POST /api/probe/start` clears `state.turns`, `state.selectedTurn`, and resets `state.followLatest = true`.
- Refreshing the browser tab clears the transcript (it's in-memory only — see `06-non-goals.md`).

## Security

All five LLM-controlled fields (`system`, `prompt`, `raw`, `raw_excerpt`, `model`) render via `node.textContent = value` — never `innerHTML`, never `insertAdjacentHTML`. This is the same rule the existing `probe-render.js` follows for the timeline; the detail panel follows the same convention. An automated test in the test suite asserts no `innerHTML` / `insertAdjacentHTML` usage in `probe-detail.js` — manual grep checks get skipped, automated ones do not.

<!-- ============================================================ -->
<!-- END 03-right-panel-ux.md -->
<!-- ============================================================ -->

---

<!-- ============================================================ -->
<!-- BEGIN 04-file-structure.md -->
<!-- ============================================================ -->

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
| `src/earn_money/dashboard/templates/index.html` | 83 lines | Add `<aside id="probe-detail">` skeleton; wrap timeline + aside in a `.probe-body` grid container | ~100 |
| `src/earn_money/dashboard/templates/static/probe.css` | 108 lines | Add grid wrapper + responsive collapse | ~140 |
| `src/earn_money/dashboard/templates/static/probe.js` | 84 lines | Add click handlers, tab toggle dispatch, follow-latest state; route `action_parsed` and new `action_parse_failed` events to dispatcher | ~140 |
| `src/earn_money/dashboard/templates/static/probe-render.js` | 84 lines | Append each `action_pending` event to `state.turns[turn].attempts`; capture `system`/`prompt` once per turn; flip `parseOutcome` on `action_parsed`/`action_parse_failed` (matched by `(turn, attempt)`) | ~150 |

## Frontend (new)

| File | Lines (budget) | Purpose |
|------|----------------|---------|
| `src/earn_money/dashboard/templates/static/probe-status.js` | ≤40 | Shared pure-function module: `window.getTurnStatus(turnState) -> string`. Loaded BEFORE `probe-render.js` and `probe-detail.js` so both can call it. No DOM access. Pure function over state |
| `src/earn_money/dashboard/templates/static/probe-detail.css` | ≤150 | Right panel layout: header, sub-tabs, attempt cards, warning border, prompt `<pre>` styling |
| `src/earn_money/dashboard/templates/static/probe-detail.js` | ≤170 | Right-panel renderer: header builder, tab switcher, delta-diff function, attempt-card builder. Calls `window.getTurnStatus()` (from `probe-status.js`). Reads from `state`, no DOM coupling to the timeline |

`probe-detail.js` is the most substantive new module. The delta-diff function (`splitPromptSections(prompt) → { sectionName: body }`, then compare two maps and keep only differing sections) is ~30 lines on its own. `probe-status.js` is intentionally tiny — a 5-branch switch over `turnState` fields.

## Server routes (modify)

`src/earn_money/dashboard/server.py` — `_STATIC_ROUTES` dict gains three entries:

```python
"/static/probe-status.js":  (_STATIC / "probe-status.js",  _JS),
"/static/probe-detail.css": (_STATIC / "probe-detail.css", _CSS),
"/static/probe-detail.js":  (_STATIC / "probe-detail.js",  _JS),
```

(`_STATIC` already resolves to `src/earn_money/dashboard/templates/static/`.) No new HTTP route. No new handler method.

`index.html` loads in this order:
1. `probe-status.js` (defines `window.getTurnStatus`)
2. `probe-render.js` (timeline; calls `window.getTurnStatus`)
3. `probe-detail.js` (right panel; calls `window.getTurnStatus`)
4. `probe.js` (dispatcher; orchestrates the others)

## Tests (modify + new)

| File | Change |
|------|--------|
| `tests/agent/test_hacker_loop.py` | Add `TestPromptHook` and `TestAttemptIdentity` classes — see `05-test-plan.md` for full case list |
| `tests/dashboard/test_probe_runner.py` | Add `TestPromptInSseEvent` and `TestAttemptIdentityInSseEvent` classes — see `05-test-plan.md` |
| `tests/dashboard/test_probe_routes.py` | Register the three new static-asset paths (`probe-status.js`, `probe-detail.css`, `probe-detail.js`); smoke-test 200 + Content-Type |
| `tests/dashboard/test_probe_detail_static.py` (**new**) | Automated grep: assert `probe-detail.js` contains no `innerHTML` or `insertAdjacentHTML`. One Python test, runs in pytest, cannot be skipped accidentally |

No frontend unit tests for rendering logic — consistent with the project today. The static safety test is the one exception (security regression, automated). Manual verification path remains in `05-test-plan.md`.

## Files NOT touched

- `src/earn_money/agent/probe_actions.py` — parsing logic unchanged
- `src/earn_money/dashboard/templates/static/{tabs.js, render.js, render_panels.js, dashboard.js}` — recon-tab and shared-component code untouched
- `src/earn_money/dashboard/templates/static/{tokens.css, dashboard.css, panels.css}` — global styles untouched
- Any non-dashboard runner, ledger, or recon code

## Total impact

- 2 server files modified (hook signatures + SSE overrides — surgical)
- 4 frontend files modified (including `index.html` load-order change)
- 3 frontend files added (`probe-status.js`, `probe-detail.css`, `probe-detail.js`)
- 3 test files modified
- 1 test file added (`test_probe_detail_static.py`)
- 1 server route file modified (three-line additions to `_STATIC_ROUTES`)

Net additions: ~360 lines of new frontend code across three files. No new dependencies. No new HTTP routes.

<!-- ============================================================ -->
<!-- END 04-file-structure.md -->
<!-- ============================================================ -->

---

<!-- ============================================================ -->
<!-- BEGIN 05-test-plan.md -->
<!-- ============================================================ -->

# Test Plan

## Automated

### `tests/agent/test_hacker_loop.py`

Add a `TestPromptHook` class:

- `test_on_llm_response_called_with_prompt_and_system_on_first_call` — runs a one-turn loop with a valid stop action; asserts the hook was called once with `attempt=1`, `used_response_format=True`, `prompt` equal to `_build_prompt()` output, and `system` equal to `_SYSTEM_PROMPT`.
- `test_on_llm_response_called_twice_on_parse_retry` — primes the provider to return garbage then valid JSON; asserts hook called twice with `attempt=1` then `attempt=2`, with `used_response_format` flipping `True → False` and the same `prompt`/`system` values both times.
- `test_on_llm_response_attempt_1_can_have_used_response_format_false` — primes the provider so the FIRST call returns valid JSON but `with_response_format` was forced to `False` (e.g., via a future code path); asserts the hook is called with `attempt=1, used_response_format=False`. **This is the test the reviewer asked for** — proves `used_response_format` is not derived from `attempt`.
- `test_on_llm_response_attempt_2_only_when_retry_fires` — valid JSON on first call; asserts hook called once (no second call).

Add a `TestAttemptIdentity` class:

- `test_on_action_parsed_carries_attempt_1_when_first_call_parses` — happy path; asserts `_on_action_parsed` is called with `attempt=1`.
- `test_on_action_parsed_carries_attempt_2_when_retry_recovers` — garbage then valid; asserts `_on_action_parsed` is called with `attempt=2, parse_recovered=True`.
- `test_on_action_parse_failed_called_with_attempt_1_when_first_attempt_fails` — garbage then valid; asserts `_on_action_parse_failed` is called once with `attempt=1` and a non-empty `error` string.
- `test_on_action_parse_failed_called_twice_when_both_attempts_fail` — garbage on both calls; asserts `_on_action_parse_failed` called twice, with `attempt=1` then `attempt=2`.
- `test_no_action_parse_failed_on_happy_path` — valid on first call; asserts `_on_action_parse_failed` was never called.

Existing `TestHooks` tests use `lambda *_a, **_k: …` and should keep working without modification — new kwargs absorbed by `**_k`. **However**, any test that constructed a `_on_action_parsed` callback with a positional signature must be updated to use `**_k`, since `attempt` is now a required kwarg.

### `tests/dashboard/test_probe_runner.py`

Add a `TestPromptInSseEvent` class:

- `test_action_pending_event_includes_full_prompt_and_system` — drives one turn; drains queue; asserts the `action_pending` event's `data` dict contains `prompt` (non-empty), `system` (non-empty), and `raw` (full response, not 200-char truncated).
- `test_action_pending_event_includes_attempt_and_used_response_format` — asserts both new fields present with `attempt=1, used_response_format=True` for a single-attempt turn.
- `test_action_pending_event_emitted_twice_when_retry_fires` — primes provider with garbage then valid; asserts two `action_pending` events with `turn=1`, first `attempt=1, used_response_format=True`, second `attempt=2, used_response_format=False`.
- `test_raw_excerpt_still_present_for_backcompat` — asserts the existing `raw_excerpt` field is still in the event (200-char cap unchanged).

Add a `TestAttemptIdentityInSseEvent` class:

- `test_action_parsed_event_carries_attempt` — happy path; asserts the `action_parsed` event's `data` dict contains `attempt=1`.
- `test_action_parsed_event_carries_attempt_2_after_retry` — garbage then valid; asserts `action_parsed` event carries `attempt=2, parse_recovered=True`.
- `test_action_parse_failed_event_emitted_on_first_failure` — garbage then valid; asserts a `turn/action_parse_failed` event is emitted with `attempt=1` and a non-empty `error`, ordered between the two `action_pending` events.
- `test_action_parse_failed_event_not_emitted_on_happy_path` — valid on first call; asserts no `action_parse_failed` event in the stream.

### `tests/dashboard/test_probe_routes.py`

In the existing `TestStaticAssets` (or equivalent) class:

- `test_serves_probe_status_js` — `GET /static/probe-status.js` → 200 + `application/javascript`.
- `test_serves_probe_detail_css` — `GET /static/probe-detail.css` → 200 + `text/css`.
- `test_serves_probe_detail_js` — `GET /static/probe-detail.js` → 200 + `application/javascript`.

### `tests/dashboard/test_probe_detail_static.py` (new file)

One automated security regression test — enforces the `textContent`-only rule for `probe-detail.js`. Replaces the easily-skipped manual grep:

```python
from pathlib import Path
import re

_JS = Path(__file__).resolve().parents[2] / "src" / "earn_money" / "dashboard" / "templates" / "static" / "probe-detail.js"
_FORBIDDEN = re.compile(r"\binnerHTML\b|\binsertAdjacentHTML\b")

def test_probe_detail_js_uses_no_innerhtml():
    """LLM-controlled strings must render via textContent only.

    `prompt` and `raw` carry target-supplied bytes (HTTP response bodies
    echoed in observations). Any innerHTML / insertAdjacentHTML in
    probe-detail.js is a security regression.
    """
    src = _JS.read_text(encoding="utf-8")
    matches = [
        (i + 1, line) for i, line in enumerate(src.splitlines())
        if _FORBIDDEN.search(line)
    ]
    assert not matches, (
        "probe-detail.js must not use innerHTML or insertAdjacentHTML — "
        f"found {len(matches)} occurrence(s): {matches}"
    )
```

This test runs in the regular `pytest` suite. Cannot be skipped, cannot be forgotten.

**Author note:** the regex matches raw bytes, including comments. **Do not mention `innerHTML` or `insertAdjacentHTML` in comments inside `probe-detail.js`** — the test will fail. If a comment needs to discuss the rule, phrase it as "use `textContent`, not the DOM-write methods" or similar. This is intentional: a stricter check is better than one that allows hand-wave exemptions, and the failure mode is just a clear test failure with a line number.

## Manual verification

### Pre-deploy local check

```bash
touch RECON_ENABLED
uv run python -m earn_money.dashboard.server --root . &
# open http://127.0.0.1:8080/, switch to Probe tab
# observe the split layout — left column = timeline, right column = empty "Waiting for first turn…" panel
```

### Live VPS check (the canonical verification)

After deploy, repeat the juice shop probe (`https://target.cocode.dk`, local_lab). Observe:

1. **Turn 1 lands.** Right panel auto-selects turn 1; header shows model + "in progress" then "complete". Delta tab shows the prompt's Session State block; Full tab shows the verbatim prompt. Response card shows the parsed action (or, for qwen, the retry pair).
2. **Turn 2 with retry.** Click turn 2 in the timeline (or let auto-follow do it). Two attempt cards stacked: `#1 with response_format` with warning border and `"encoding=UTF-8"` response; `#2 without response_format` with default border and the parsed `{"tool":"get",…}`.
3. **Tab switching.** Toggle between Delta and Full while on turn 2 — Full shows the entire prompt; Delta shows only the new Session State (the previous turn's observation appears as new context).
4. **Selection sticks.** Click turn 1, wait for turn 3 to arrive — panel stays on turn 1 and the `↓ follow latest` button appears.
5. **Follow-latest resumes.** Click `↓ follow latest` — panel jumps to turn 3.
6. **After done.** Probe completes; transcript stays visible; can still click any turn and toggle tabs.
7. **Restart.** Start a new probe — transcript clears, follow-latest re-engages.

## Security regression check

Covered by the automated test `tests/dashboard/test_probe_detail_static.py::test_probe_detail_js_uses_no_innerhtml` (see above). The manual grep that lived here in v1 of this spec has been promoted to a pytest-level assertion so it cannot be skipped.

For belt-and-braces, the same grep can be added as a `pre-commit` hook entry — that is **optional** and not blocking; the pytest gate is the authoritative one.

<!-- ============================================================ -->
<!-- END 05-test-plan.md -->
<!-- ============================================================ -->

---

<!-- ============================================================ -->
<!-- BEGIN 06-non-goals.md -->
<!-- ============================================================ -->

# Non-Goals

Things this change explicitly does NOT do. Each is excluded for a reason; the reason is the test for "should we reconsider?".

## Cross-page persistence

Refreshing the browser tab clears the transcript. The detail panel renders from in-memory `state.turns` populated by the live SSE stream; there is no `localStorage` snapshot, no server-side prompt cache, no API to fetch a past run's prompts.

**Reason:** Adds server-side storage (per-run, per-turn prompt blob = ~5 KB × turns × runs). The dashboard already has SQLite per program; introducing a "live run history" table is a feature, not a debugging aid. Operators who need persistence today can copy-paste from the panel into a note.

**Reconsider when:** Operators report losing context after a browser crash mid-debug.

## Cross-run transcript history

The panel shows only the current run. The next `POST /api/probe/start` clears `state.turns`. There is no "browse past runs" UI.

**Reason:** Same as above — requires server-side storage. Also, comparing prompts across runs is a longer-term observability play; not what this change is for.

## Server-side prompt diffing

The Delta tab computes "what's new this turn" entirely in the browser. The server sends full prompts; the client splits on `=== ` headers and shows only differing sections.

**Reason:** Keeps the server stateless. Splitting is ~30 lines of JS; doing it server-side would add a per-turn diff payload to the SSE event for no UX gain.

## Token / cost accounting

The existing `estimated_tokens` field (a crude `len(text) // 4`) is unchanged. We do NOT add prompt-token counts, completion-token counts, OpenRouter cost lookups, or a per-run cost meter.

**Reason:** Out of scope. The retry-attempt visibility this change delivers is enough to inform a future "model X is wasting calls" decision; cost dashboards are a separate feature.

## Mobile-first layout

The grid collapses to a single column on narrow viewports as a graceful-fail safety, not as a designed mobile experience. We do not test on phones, do not optimise touch targets, and do not commit to mobile usability.

**Reason:** Dashboard runs on operator laptop or VPS-served-to-laptop. Mobile is not a use case.

## Sanitization beyond `textContent`

We rely entirely on `node.textContent = value` to neutralise LLM-controlled strings in the DOM. We do NOT add HTML escaping libraries, content-security-policy headers, or sanitization wrappers.

**Reason:** `textContent` is the correct primitive. Adding a sanitizer would be defence-in-depth against an `innerHTML` bug we don't have; the existing code follows the same rule. The automated grep test (`test_probe_detail_static.py`) is the discipline.

## Prompt editing / replay

The panel is read-only. We do NOT add "edit this prompt and send it to the model" or "replay this turn with a different model".

**Reason:** That's a fundamentally different feature (LLM playground vs probe observability) and would require new server endpoints, new safety review (replay against the same target counts as a new request that needs RoE checks), and a much bigger spec.

## Animation / transitions

No fade-ins, no slide animations, no skeleton loaders. The panel updates instantly on event arrival.

**Reason:** SSE events arrive at human-readable cadence (one per LLM round-trip). Animations would obscure rather than aid comprehension. Consistent with the rest of the dashboard's no-animation style.

## Copy / "copy to clipboard" buttons

No "copy prompt", "copy response", or "copy this turn as JSON" affordances. The user copies via browser selection (`Ctrl+A` inside the scrollable `<pre>`, or click-drag).

**Reason:** Clipboard APIs introduce permission prompts, browser-version edge cases, and accidental-secret-exposure surface (one wrong button-target binding and you've copied the wrong attempt). The selection-and-copy fallback works today and costs nothing. Revisit if operators report friction.

## Hard truncation of `prompt`, `system`, or `raw`

The server never truncates these fields. If a misbehaving model produces a 250-KB `raw`, the full 250 KB ships over SSE and lives in browser memory.

**Reason:** Observability is the entire point of this feature. Hard truncation defeats the goal — the operator would see "(truncated)" exactly when the model is misbehaving most interestingly. The right escape hatch (if size ever becomes a real problem in practice) is a UI affordance like "this field is 250 KB, click to expand" with the full value preserved in memory — not a server-side cap. That escape hatch is deferred to a future revision and is gated on observing a real performance issue.

## Server-side `request` metadata object

No `temperature`, `max_tokens`, `response_format_type`, or other provider kwargs in the SSE payload. The operator currently needs to know "did `response_format` go out, yes/no?" — and `used_response_format: bool` answers that.

**Reason:** Gold-plating. The current debugging goal is concrete (the qwen `response_format` retry pattern); adding a `request: {…}` object now means designing what goes in it across providers we don't yet support. Defer until a debugging task forces it.

<!-- ============================================================ -->
<!-- END 06-non-goals.md -->
<!-- ============================================================ -->
