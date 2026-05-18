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

Loading order for the JS files (the helper must be defined before any caller) is in `04-file-structure.md § Server routes`. No status field is stored on `state.turns[N]` — always derived.

### Run-level errors

The existing `probe_error` SSE event is run-level, not per-turn — it fires when the runner itself crashes (provider not reachable, internal exception, etc.). It is rendered as a banner at the top of the Probe tab, OUTSIDE the detail panel and OUTSIDE any per-turn status. `getTurnStatus` never sees a `probe_error`. `state.runError = "..."` lives at the top of state; `probe.js` renders it.

This keeps the per-turn enum tight and matches operator mental model: a run that errored out is a run-level event ("the whole probe blew up"), not a turn-level outcome.

## Boundary discipline

One responsibility per module. Per-file purpose + exports live in `04-file-structure.md`; the rules below are the cross-module invariants:

- **Only `probe-state.js` writes to `state`.** Renderers read `window.probeState`; the dispatcher (`probe.js`) does not read state at all.
- **Single render trigger.** The reducer's `onChange` callback (registered by `probe.js` at boot) is the only thing that triggers a render. `probe.js` does NOT call render manually after `probeReducer()`.
- **Renderers do not call each other.** Timeline and detail panel share only `probe-status.js`.

### Reset API

When the operator starts a new probe, `probe.js` fires a synthetic event `{stage: "probe_start"}` through `window.probeReducer()`. The reducer clears `state.turns`, `state.selectedTurn`, `state.runError` and resets `state.followLatest=true`, then fires `onChange`. `probe.js` MUST NOT clear state directly.
