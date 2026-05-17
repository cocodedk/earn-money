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
- Retry attempts shown stacked, labelled, colour-coded.

Out of scope:
- Persisting prompts/responses across page reloads. The transcript lives in browser memory for the run; refreshing the page loses it.
- Per-program prompt history across runs. One run, one transcript.
- Server-side prompt diffing or storage — diff is computed in the browser.
- Cost/token accounting beyond the existing per-turn `estimated_tokens`.

See `06-non-goals.md` for the full exclusion list.

## References

- [`01-architecture.md`](01-architecture.md) — server + client overview
- [`02-sse-event-shape.md`](02-sse-event-shape.md) — wire format
- [`03-right-panel-ux.md`](03-right-panel-ux.md) — layout, tabs, retry stacking
- [`04-file-structure.md`](04-file-structure.md) — files to create/modify, line budgets
- [`05-test-plan.md`](05-test-plan.md) — tests and manual verification
- [`06-non-goals.md`](06-non-goals.md) — explicit exclusions
