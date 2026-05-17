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
- Outcome from `state.turns[N].complete` if known, else "in progress"
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

## Retry stacking

Both Delta and Full tabs render the **per-attempt** cards below the prompt section. One card per element of `state.turns[selectedTurn].attempts`, in order.

```
┌─ Attempt #1 · with response_format ─────────────────┐
│ Prompt:                                              │
│ [prompt block — Delta or Full per tab]               │
│ Response:                                            │
│ "{"                                                  │
│ ⚠ parse failed                                       │
└──────────────────────────────────────────────────────┘
┌─ Attempt #2 · without response_format ──────────────┐
│ Prompt:                                              │
│ [same prompt — repeated literally; second call sent  │
│  the same `user=` arg, only `response_format` kwarg  │
│  differs]                                            │
│ Response:                                            │
│ {"tool":"get","category":"http_get","args":{…}}      │
│ ✓ parsed                                             │
└──────────────────────────────────────────────────────┘
```

Garbage / failed-parse responses get a warning border (CSS `--color-warning`). Successful parses get the default border. Status (✓ / ⚠) is derived from whether a matching `turn/action_parsed` event arrived for the same `turn` after this `action_pending`.

For the common case where the same prompt is sent to both attempts, the Prompt block in the second card may collapse to "(same prompt as attempt #1)" to avoid scrolling past a duplicate — implementation may include a small expand toggle. Keep simple for v1: render both verbatim; revisit if it's annoying.

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

All four LLM-controlled fields (`prompt`, `raw`, `raw_excerpt`, `model`) render via `node.textContent = value` — never `innerHTML`, never `insertAdjacentHTML`. This is the same rule the existing `probe-render.js` follows for the timeline; the detail panel follows the same convention.
