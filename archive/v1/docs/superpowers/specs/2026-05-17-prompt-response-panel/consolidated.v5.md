# Prompt & Response Detail Panel — Consolidated Spec

**Version:** v5
**Source folder:** `docs/superpowers/specs/2026-05-17-prompt-response-panel/`
**Consolidated:** 2026-05-17
**Supersedes:** `consolidated.v4.md`

## Changes from v4 (round 4 — all 8 findings adopted, no new sections)

| # | Fix |
|---|-----|
| 1 | Helper layering disambiguated (`_call_provider_with_rf_fallback` is module helper, `_get_llm_response` is wrapper); new hook test + SSE test for the case where the helper's internal fallback fires on attempt 1 |
| 2 | One render trigger: `probe-state.js` calls `onChange`; `probe.js` registers it once and never re-renders manually after `probeReducer` |
| 3 | Reset API: `probe.js` fires synthetic `{stage: "probe_start"}` event; reducer clears state; `probe.js` MUST NOT mutate state directly |
| 4 | `probe_state.test.js` (Node `--test`) replaces the Python mirror; pytest wrapper skips if `node` missing; tests the shipped JS |
| 5 | `window.formatTurnStatus(status)` added; both renderers use it; manual verification text fixed (no `"complete"` enum value) |
| 6 | `probe.js` does NOT read or write state. Renderers read `window.probeState` directly |
| 7 | Forbidden-sinks regex extended to `outerHTML`, `document.write`, `createContextualFragment` |
| 8 | Delta tab falls back to full prompt + "could not compute delta" label if heading whitelist matches nothing |

Net source change vs v4: ~+50 lines, no new sections. All source files still under 200 (test plan at 202 — within the spec exemption).

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
4. **Status enum AND display text come from one helper each.** `window.getTurnStatus(turn) -> enum` (explicit priority order, five values) and `window.formatTurnStatus(status) -> string` (fixed lookup table) both live in `probe-status.js`. Both renderers call them — no local string mapping anywhere. JS-tested.
5. **State is owned by one module.** `probe-state.js` is the single writer to all state fields, including reset via `probe_start` event. Both renderers are strictly read-only over `window.probeState`. `probe.js` neither reads nor writes state; render is triggered solely by the reducer's `onChange` callback. JS-tested (reducer suite).
6. **Prompt rendered once per turn.** Attempt cards show only per-attempt metadata + response + parse status. Prompt is NOT duplicated across attempt cards (the retry uses the same prompt — duplication is pure noise).
7. **`probe-detail.js` has no `innerHTML` or `insertAdjacentHTML`.** Enforced by an automated test, not just a manual grep.
8. **`raw` and `prompt` are never truncated at the server.** The UI renders them in a scrollable `<pre>`. A test using a >200-char raw response proves the server keeps the full value (not just the 200-char excerpt).
9. **`index.html` script + CSS loading is correct and asserted.** `probe-detail.css` is linked; JS files load in dependency order (`probe-status.js` → `probe-state.js` → `probe-render.js` → `probe-detail.js` → `probe.js`). An automated test parses `index.html` and asserts both.

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

**Helper layering (current code):** `_call_provider_with_rf_fallback(provider, *, system, user, task, with_response_format) -> (raw, used_rf)` is the module-level helper that owns the `response_format` fallback logic. `_get_llm_response(prompt, *, with_response_format)` is the instance-method wrapper that calls it from inside `HackerLoop` / `ProbeRunner`.

**Implementation rule (avoids a subtle future bug):** `_get_llm_response` should return `(raw, used_response_format)` as a tuple — pass the helper's return value through unchanged — and the caller in `run()` should pass `used_response_format` directly into the hook call. Do not route through `self._last_used_response_format`. Routing through instance state works today, but any future provider call between the helper return and the hook invocation would silently clobber it.

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

A single helper lives in its own tiny shared file, `probe-status.js`. Concrete priority algorithm — the order matters:

```js
// src/earn_money/dashboard/templates/static/probe-status.js
window.getTurnStatus = function getTurnStatus(turn) {
  if (!turn) return "in_progress";

  // Policy block beats parse outcomes — operator cares "was this blocked?"
  // even if the LLM call itself parsed cleanly.
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
```

Return values: `"in_progress" | "ok" | "recovered" | "parse_failed" | "policy_blocked"` — **five values, not six.** Run-level errors are handled separately (see "Run-level errors" below); `getTurnStatus` never returns `"error"`.

**Display text comes from one mapping too.** `probe-status.js` also exposes `window.formatTurnStatus(status) -> string`, a fixed lookup table from enum value to header/badge text (e.g. `"recovered"` → `"invalid_action → recovered"`, `"ok"` → `"ok"`). Both renderers MUST call this — no local string mapping in either. Keeps timeline and detail header textually identical.

**Loading rule:** `index.html` loads `probe-status.js` BEFORE both `probe-render.js` (timeline) and `probe-detail.js` (right panel). The dashboard JS is plain `<script>` tags (not ES modules), so the helper is exposed on `window` and load order is the contract.

Both the timeline summary and the detail header call `window.getTurnStatus()`. The status enum maps to display text (e.g. `"recovered"` → `"invalid_action → recovered"`) inside each renderer. No status field is stored on `state.turns[N]` — always derived.

### Run-level errors

The existing `probe_error` SSE event is run-level, not per-turn — it fires when the runner itself crashes (provider not reachable, internal exception, etc.). It is rendered as a banner at the top of the Probe tab, OUTSIDE the detail panel and OUTSIDE any per-turn status. `getTurnStatus` never sees a `probe_error`. `state.runError = "..."` lives at the top of state; `probe.js` renders it.

This keeps the per-turn enum tight and matches operator mental model: a run that errored out is a run-level event ("the whole probe blew up"), not a turn-level outcome.

## Boundary discipline

- **Status helper** (`probe-status.js`) — pure function. No DOM, no state mutation. Loaded first. Also exposes `window.formatTurnStatus(status)` for display-text mapping.
- **State reducer** (`probe-state.js`) — **owns `state` entirely.** Handles every event: appends attempts on `action_pending`, captures `system`/`prompt`/`raw`/`model`, flips `parseOutcome` on `action_parsed`/`action_parse_failed` (matched by `(turn, attempt)`), updates `policyDecision`/`observation`/`complete` on policy/observation/complete events, sets `state.runError` on `probe_error`, clears all state on `probe_start` (synthetic event fired by `probe.js` when a new run begins — see "Reset API" below). Manages `selectedTurn`/`followLatest`/`activeTab`. Exposes `window.probeState`, `window.probeReducer(event)`, and lifecycle helpers `setSelectedTurn(n)` / `setActiveTab(t)` / `setFollowLatest(b)`. Calls a registered `onChange` callback after every mutation. **Renderers do not mutate state.**
- **Timeline renderer** (`probe-render.js`) — read-only over `window.probeState`. Renders the left column. Calls `window.getTurnStatus()` and `window.formatTurnStatus()`.
- **Detail panel renderer** (`probe-detail.js`) — read-only over `window.probeState`. Renders the right column. Calls `window.getTurnStatus()` and `window.formatTurnStatus()`.
- **Probe dispatcher** (`probe.js`) — DOM event handlers (timeline clicks, tab toggles, follow-latest button, "start probe" form submit). Wires the EventSource to forward each SSE event to `window.probeReducer(event)`. **Does NOT read or write `state`** — the only render trigger is the `onChange` callback `probe.js` registers with `probe-state.js` at boot. `probe.js` does NOT call render manually after `probeReducer()`; the reducer's `onChange` is the single render trigger.

### Reset API

When the operator starts a new probe (`POST /api/probe/start` succeeds), `probe.js` fires a synthetic event `{stage: "probe_start"}` through `window.probeReducer()`. The reducer handles this by clearing `state.turns = {}`, `state.selectedTurn = null`, `state.followLatest = true`, `state.runError = null` (then calling `onChange` so renderers repaint empty). `probe.js` MUST NOT mutate `state.turns` (or any other state field) directly to clear it — the reducer is the only writer.

Strict rule: only `probe-state.js` writes to `state`. Renderers and the dispatcher only read it (renderers via `window.probeState`; the dispatcher does not read at all).

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
- Status text: renderer calls `window.getTurnStatus(turn)` to get the enum, then `window.formatTurnStatus(status)` to get the display string. Both helpers live in `probe-status.js`. Neither renderer maps the enum to display text locally. Run-level errors (probe crash) render as a banner above the whole panel, not inside the per-turn header.
- Retry indicator (`↻ retried` badge) if `attempts.length > 1`

If no turn is selected (initial state, no events yet), header shows `"Waiting for first turn…"` and tabs are disabled.

## Sub-tabs

Two buttons: **Delta** (default) and **Full**. Selecting a tab persists across turn changes — clicking turn 5 while on the Full tab keeps Full active.

### Delta tab

Splits both the previous turn's prompt and the current turn's prompt by scanning for a **fixed whitelist** of known prompt headings, in expected order:

```
=== Rules of Engagement ===
=== Session State ===
=== Available actions ===
```

Anything before the first match is the system intro section. Lines that happen to start with `===` but are NOT in the whitelist (e.g. target-controlled response bytes that include `=== Welcome ===`) stay inside the current section — they are not treated as section boundaries. This is important because the prompt embeds HTTP response bodies in the Session State block, and a malicious or just unusual target could echo our heading format.

For each whitelisted heading, if the bodies of that section differ between previous and current turn, render the current turn's section. If identical, omit. In practice this is always just the Session State block — RoE doesn't change mid-run, action menu is constant, system intro is constant.

If the selected turn is turn 1, Delta shows the entire prompt (no previous turn to diff against) with a small label "first turn — no delta".

**Fallback for prompt format drift:** if either prompt cannot be split into the expected sections (zero whitelisted headings matched), Delta renders the entire current prompt with a small label "could not compute delta". This protects against a future prompt-format change leaving Delta silently empty.

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

Status comes from `attempts[i].parseOutcome`, which **`probe-state.js` (the reducer)** sets when `turn/action_parsed` (`"ok"`) or `turn/action_parse_failed` (`"failed"`) arrives — matched by `(turn, attempt)`, never inferred from event order. The error string in `⚠ parse failed: <error>` comes from `attempts[i].parseError`, populated from the `action_parse_failed.error` field; it is `null` for `"ok"` and `"pending"` attempts. The detail panel renderer is strictly read-only over this state — see `01-architecture.md` boundary discipline.

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
| `tests/frontend/probe_state.test.js` (**new**) | Reducer + status-helper tests for the shipped JS. Run via `node --test` (built into Node 18+). Invoked from pytest via a tiny subprocess wrapper that skips with a clear message if `node` is not on PATH (zero new Python deps; one optional system dep). Covers reducer cases enumerated in `05-test-plan.md` plus `getTurnStatus`/`formatTurnStatus`. Tests the actually-shipped JS — no Python mirror to drift |

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
- 2 test files added (`test_probe_static_assets.py`, `probe_state.test.js` — Node-runnable)
- 1 server route file modified (four-line additions to `_STATIC_ROUTES`)

Net additions: ~500 lines of new frontend code across four files. No new dependencies. No new HTTP routes. The architectural cleanup (state owner separated from renderers) makes the file count higher than v3 but each file is single-purpose and well under 200 lines.

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
- `test_on_llm_response_attempt_2_only_when_retry_fires` — valid JSON on first call; asserts hook called once (no second call).
- `test_on_llm_response_attempt_1_used_response_format_false_when_provider_rejects_rf` — provider's first call (with `response_format`) raises; helper internally falls back without `response_format` and succeeds. Asserts the hook is called ONCE with `attempt=1, used_response_format=False` — proves the value flows end-to-end (helper → wrapper → hook) when the fallback happens inside a single `_get_llm_response` call.

Add a `TestProviderHelper` class — these target `_call_provider_with_rf_fallback` directly, not through `run()`. The point is to prove `used_response_format` reflects what the helper actually sent, decoupled from attempt number:

- `test_helper_returns_used_response_format_true_when_rf_succeeds` — `with_response_format=True`, provider returns valid JSON; helper returns `(raw, True)`.
- `test_helper_returns_used_response_format_false_when_caller_passes_false` — `with_response_format=False`, provider returns valid JSON; helper returns `(raw, False)`. **This is the test the reviewer asked for** — proves the field is per-call truth, not derived from a position counter. No production code change needed; the helper already accepts `with_response_format=False` as a kwarg.
- `test_helper_returns_used_response_format_false_when_rf_call_raises` — `with_response_format=True`, first provider call raises (simulating provider rejection of `response_format`); helper falls back to a second call without rf and returns `(raw, False)`.

Add a `TestAttemptIdentity` class:

- `test_on_action_parsed_carries_attempt_1_when_first_call_parses` — happy path; asserts `_on_action_parsed` is called with `attempt=1`.
- `test_on_action_parsed_carries_attempt_2_when_retry_recovers` — garbage then valid; asserts `_on_action_parsed` is called with `attempt=2, parse_recovered=True`.
- `test_on_action_parse_failed_called_with_attempt_1_when_first_attempt_fails` — garbage then valid; asserts `_on_action_parse_failed` is called once with `attempt=1` and a non-empty `error` string.
- `test_on_action_parse_failed_called_twice_when_both_attempts_fail` — garbage on both calls; asserts `_on_action_parse_failed` called twice, with `attempt=1` then `attempt=2`.
- `test_no_action_parse_failed_on_happy_path` — valid on first call; asserts `_on_action_parse_failed` was never called.

Existing `TestHooks` tests use `lambda *_a, **_k: …` and should keep working without modification — new kwargs absorbed by `**_k`. **However**, any test that constructed a `_on_action_parsed` callback with a positional signature must be updated to use `**_k`, since `attempt` is now a required kwarg.

### `tests/dashboard/test_probe_runner.py`

Add a `TestPromptInSseEvent` class:

- `test_action_pending_event_includes_full_prompt_and_system_with_long_raw` — drives one turn where the provider returns a **>250-char raw response** (e.g., `'{"tool":"stop","category":"stop","args":{"reason":"' + "x" * 250 + '"}}'`); drains queue; asserts:
    - `data["prompt"]` is non-empty
    - `data["system"]` is non-empty
    - `data["raw"] == full_raw` (exact equality; no truncation)
    - `data["raw_excerpt"] == full_raw[:200]`
    - `len(data["raw"]) > len(data["raw_excerpt"])` — guards against the case where a short mocked response would make truncation a no-op and falsely "pass" the test.
- `test_action_pending_event_includes_attempt_and_used_response_format` — asserts both new fields present with `attempt=1, used_response_format=True` for a single-attempt turn.
- `test_action_pending_event_emitted_twice_when_retry_fires` — primes provider with garbage then valid; asserts two `action_pending` events with `turn=1`, first `attempt=1, used_response_format=True`, second `attempt=2, used_response_format=False`.
- `test_action_pending_event_carries_used_response_format_false_when_provider_rejects_rf` — provider's first call raises; helper falls back internally. Asserts a SINGLE `action_pending` event for the turn with `attempt=1, used_response_format=False` — proves the value reaches the SSE wire, not just the hook.
- `test_raw_excerpt_still_present_for_backcompat` — asserts the existing `raw_excerpt` field is still in the event (200-char cap unchanged).

Add a `TestAttemptIdentityInSseEvent` class:

- `test_action_parsed_event_carries_attempt` — happy path; asserts the `action_parsed` event's `data` dict contains `attempt=1`.
- `test_action_parsed_event_carries_attempt_2_after_retry` — garbage then valid; asserts `action_parsed` event carries `attempt=2, parse_recovered=True`.
- `test_action_parse_failed_event_emitted_on_first_failure` — garbage then valid; asserts a `turn/action_parse_failed` event is emitted with `attempt=1` and a non-empty `error`, ordered between the two `action_pending` events.
- `test_action_parse_failed_event_not_emitted_on_happy_path` — valid on first call; asserts no `action_parse_failed` event in the stream.

### `tests/dashboard/test_probe_routes.py`

In the existing `TestStaticAssets` (or equivalent) class:

- `test_serves_probe_status_js` — `GET /static/probe-status.js` → 200 + `application/javascript`.
- `test_serves_probe_state_js` — `GET /static/probe-state.js` → 200 + `application/javascript`.
- `test_serves_probe_detail_css` — `GET /static/probe-detail.css` → 200 + `text/css`.
- `test_serves_probe_detail_js` — `GET /static/probe-detail.js` → 200 + `application/javascript`.

### `tests/dashboard/test_probe_static_assets.py` (new file)

Three cheap regex-based static-file assertions. Replaces the easily-skipped manual grep AND closes the script-order / CSS-link gaps the reviewer flagged:

```python
from pathlib import Path
import re

_BASE = Path(__file__).resolve().parents[2] / "src" / "earn_money" / "dashboard" / "templates"
_STATIC = _BASE / "static"
_INDEX = _BASE / "index.html"

_FORBIDDEN = re.compile(
    r"\binnerHTML\b|\binsertAdjacentHTML\b|\bouterHTML\b"
    r"|\bdocument\.write\b|\bcreateContextualFragment\b"
)

_EXPECTED_SCRIPT_ORDER = [
    "/static/probe-status.js",
    "/static/probe-state.js",
    "/static/probe-render.js",
    "/static/probe-detail.js",
    "/static/probe.js",
]


def test_probe_detail_js_uses_no_html_sinks():
    """LLM-controlled strings must render via textContent only."""
    src = (_STATIC / "probe-detail.js").read_text(encoding="utf-8")
    matches = [
        (i + 1, line) for i, line in enumerate(src.splitlines())
        if _FORBIDDEN.search(line)
    ]
    assert not matches, (
        "probe-detail.js must not use HTML-write sinks "
        "(innerHTML, insertAdjacentHTML, outerHTML, document.write, "
        f"createContextualFragment) — found {len(matches)} occurrence(s): {matches}"
    )


def test_index_html_loads_probe_detail_css():
    """The new panel CSS must be linked in index.html, or the panel ships unstyled."""
    html = _INDEX.read_text(encoding="utf-8")
    assert '"/static/probe-detail.css"' in html, (
        "index.html must <link> to /static/probe-detail.css"
    )


def test_index_html_loads_probe_scripts_in_dependency_order():
    """probe-status.js must load before probe-state.js, before the renderers, before probe.js."""
    html = _INDEX.read_text(encoding="utf-8")
    found = re.findall(r'<script[^>]+src="(/static/probe[^"]+\.js)"', html)
    assert found == _EXPECTED_SCRIPT_ORDER, (
        f"index.html script order must be {_EXPECTED_SCRIPT_ORDER}, got {found}"
    )
```

All three run in the regular `pytest` suite. Cannot be skipped.

**Author note on the HTML-sink test:** the regex matches raw bytes, including comments. Do not mention any of the forbidden sink names in `probe-detail.js` comments — the test will fail. Phrase comments as "use `textContent`" or "no DOM-write methods" instead. The strictness is deliberate.

### `tests/frontend/probe_state.test.js` + `tests/frontend/test_probe_state_runner.py` (new)

Tests the **shipped JS** — both `probe-state.js` (the reducer) and `probe-status.js` (the two helpers). Runs via Node's built-in test runner (`node --test`, no new deps for Node 18+). A tiny pytest wrapper invokes Node as a subprocess and surfaces failures; if `node` is not on PATH the wrapper skips with a clear message.

Pytest wrapper (`test_probe_state_runner.py`):

```python
import shutil, subprocess
import pytest

def test_probe_state_js_suite():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH — install Node 18+ to run the JS test suite")
    result = subprocess.run(
        [node, "--test", "tests/frontend/probe_state.test.js"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
```

`probe_state.test.js` cases (each `test()` block in the file):

**`probeReducer` — attempt matching:**
- `action_pending` for turn 1 attempt 1 → state.turns[1].attempts has one entry with `parseOutcome="pending"`.
- `action_parse_failed` for turn 1 attempt 1 → that attempt becomes `failed` with `parseError` set; no second attempt created.
- Subsequent `action_pending` for turn 1 attempt 2 → second attempt appended as `pending`; first attempt unchanged.
- `action_parsed` for turn 1 attempt 2 → only attempt 2 flips to `ok`; attempt 1 stays `failed`.
- `getTurnStatus(state.turns[1])` after the above sequence returns `"recovered"`.

**`probeReducer` — selection / follow-latest:**
- `setSelectedTurn(2)` sets `state.selectedTurn=2` AND `state.followLatest=false`.
- After `setSelectedTurn(2)`, a new `action_pending` for turn 3 does NOT change `selectedTurn`.
- `setFollowLatest(true)` re-enables auto-follow and re-selects the latest turn.

**`probeReducer` — run-level:**
- `probe_error` event sets `state.runError` and does NOT change any `state.turns[N]` field.
- `probe_start` event clears `state.turns`, `state.selectedTurn`, `state.runError`; resets `state.followLatest=true`.

**`probeReducer` — robustness:**
- Event with unknown `stage` is ignored silently (no exception, no state change).
- `onChange` callback fires exactly once per accepted event.

**`getTurnStatus` priority + `formatTurnStatus`:**
- Null turn → `"in_progress"`.
- Pending attempts + `complete=false` → `"in_progress"`.
- Single `ok` attempt + `complete=true` → `"ok"`.
- One `failed` then one `ok` → `"recovered"`.
- All `failed` → `"parse_failed"`.
- One `ok` + `policyDecision.allowed=false` → `"policy_blocked"` (priority beats `"ok"`).
- One `failed` + one `ok` + `policyDecision.allowed=false` → `"policy_blocked"` (priority beats `"recovered"`).
- `formatTurnStatus("recovered") === "invalid_action → recovered"` (and one assertion per enum value).

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

1. **Turn 1 lands.** Right panel auto-selects turn 1; header shows model + status text (initially `"in_progress"`, then the final status from `formatTurnStatus()` — e.g. `"ok"` or `"recovered"`). Delta tab shows the prompt's Session State block; Full tab shows the verbatim prompt. Response card shows the parsed action (or, for qwen, the retry pair).
2. **Turn 2 with retry.** Click turn 2 in the timeline (or let auto-follow do it). Two attempt cards stacked: `#1 with response_format` with warning border and `"encoding=UTF-8"` response; `#2 without response_format` with default border and the parsed `{"tool":"get",…}`.
3. **Tab switching.** Toggle between Delta and Full while on turn 2 — Full shows the entire prompt; Delta shows only the new Session State (the previous turn's observation appears as new context).
4. **Selection sticks.** Click turn 1, wait for turn 3 to arrive — panel stays on turn 1 and the `↓ follow latest` button appears.
5. **Follow-latest resumes.** Click `↓ follow latest` — panel jumps to turn 3.
6. **After done.** Probe completes; transcript stays visible; can still click any turn and toggle tabs.
7. **Restart.** Start a new probe — transcript clears, follow-latest re-engages.

## Security regression check

Covered by the automated test `tests/dashboard/test_probe_static_assets.py::test_probe_detail_js_uses_no_html_sinks` (see above). The manual grep that lived here in v1 of this spec has been promoted to a pytest-level assertion so it cannot be skipped.

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
