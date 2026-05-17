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
