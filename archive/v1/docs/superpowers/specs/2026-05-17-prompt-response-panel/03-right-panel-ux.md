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

LLM-controlled fields render via `textContent` only. Canonical rule + enforcement: see `02-sse-event-shape.md § Security` and `05-test-plan.md::test_probe_detail_js_uses_no_html_sinks`.
