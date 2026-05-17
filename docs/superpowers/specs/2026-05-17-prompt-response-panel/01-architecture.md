# Architecture

The change is **purely additive**. No protocol breakage, no new server route, no per-run state cache.

## Server-side

### `HackerLoop._on_llm_response` hook

Today's signature:

```python
def _on_llm_response(self, turn: int, raw: str | None, model_id: str | None) -> None: ...
```

New signature:

```python
def _on_llm_response(
    self,
    turn: int,
    raw: str | None,
    model_id: str | None,
    *,
    prompt: str,
    attempt: int,                  # 1 = first call, 2 = retry-without-rf
    used_response_format: bool,    # what the call actually sent
) -> None: ...
```

The two call sites in `HackerLoop.run()` already have `prompt` in scope (it's built once per turn via `_build_prompt()`). `attempt` and `used_response_format` come from existing locals: the first call is always `attempt=1`, the retry is always `attempt=2`. `used_response_format` is read from `self._last_used_response_format` (set by the helper in `hacker_loop.py`).

### `ProbeRunner._on_llm_response` override

Overrides emit the new SSE fields directly. Signature matches the base class.

### Single source of truth

There is **no new HTTP route**. Prompts ride the existing `/api/probe/stream` SSE channel as part of each `turn/action_pending` event. Server keeps no per-run prompt cache; once the event is sent, the prompt is the browser's responsibility.

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
    attempts: [
      { prompt, raw, model, used_response_format, attempt, ts, parse_recovered }
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

Each incoming `turn/action_pending` event is **appended** to the matching turn's `attempts` array (creating the turn entry if it doesn't exist). The right panel re-renders when `selectedTurn`, `activeTab`, or the selected turn's `attempts` changes.

## Boundary discipline

- **Timeline renderer** owns left-column state. Reads `state.turns` only to know which turns exist and their summary (model, outcome).
- **Detail panel renderer** owns right-column state. Reads `state.turns[selectedTurn]` only.
- **Probe dispatcher** (`probe.js`) owns selection + tab state. Re-emits change events for both renderers.

The two renderers do not call each other.
