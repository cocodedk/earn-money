# 00 — Probe Live Tab — Overview

**Status**: draft · 2026-05-16
**Owner**: Babak Bandpey
**Branch**: `feat/run-target-script` (sequenced after the LLM-LOOP work)

## Goal

Add a second tab — **PROBE** — to the existing dashboard so the operator can launch `probe-target` against any URL and watch the `HackerLoop` execute live, turn by turn, with per-step visibility (LLM response, policy decision, HTTP observation, finding promotion) streamed over Server-Sent Events.

## What changes vs. the existing repo

- `src/earn_money/agent/task_router.py` — add **one** new `TaskType`: `AGENT_PLANNING`. The other 5 stay as they are. (Detail: [03-task-routing.md](03-task-routing.md).)
- `src/earn_money/agent/hacker_loop.py` — add **six** no-op observation hooks (`_on_llm_response`, `_on_action_parsed`, `_on_policy_decision`, `_on_observation`, `_on_finding`, `_on_turn_complete`) and tweak `_SYSTEM_PROMPT` to include an explicit "authorized testing context" paragraph. (Detail: [02-hacker-loop-hooks.md](02-hacker-loop-hooks.md).)
- `src/earn_money/agent/probe_actions.py` — add `parse_action_with_recovery(raw)` that returns `(action, parse_recovered)`; keep `parse_action(raw)` as a thin wrapper that drops the flag so the existing CLI signature is unchanged. (Detail: [04-robust-action-parsing.md](04-robust-action-parsing.md).)
- `src/earn_money/dashboard/probe_runner.py` *(new)* — subclasses `HackerLoop`, overrides the hooks to push events onto a `queue.Queue`, picks the `task` per turn from observation/action context. (Detail: [05-probe-runner.md](05-probe-runner.md).)
- `src/earn_money/dashboard/server.py` — two new routes: `POST /api/probe/start`, `GET /api/probe/stream`. (Detail: [06-server-routes.md](06-server-routes.md).)
- `src/earn_money/dashboard/templates/index.html` — tab bar above existing sections, two `<div id="tab-…">` wrappers.
- `src/earn_money/dashboard/templates/static/tabs.js` *(new)* — pure client-side tab switching, `location.hash` persistence.
- `src/earn_money/dashboard/templates/static/probe.js` *(new)* — form submit, `EventSource` client, dispatches events to `probe-render.js`.
- `src/earn_money/dashboard/templates/static/probe-render.js` *(new)* — DOM renderers (`appendTurnCard` / `appendFinding` / `markComplete` / `showError`). All values via `textContent`.
- `src/earn_money/dashboard/templates/static/probe.css` *(new)* — timeline / turn-card / badge styles, reuses `tokens.css` design tokens.
- `.env.example` — entry for `OPENROUTER_MODEL_AGENT_PLANNING`.
- `tests/dashboard/test_probe_runner.py` *(new)*, `tests/dashboard/test_probe_routes.py` *(new)*.

## What does NOT change

- The CLI: `bin/probe-target` and `bin/run-target` keep working unchanged. The dashboard is an alternate entry point, not a replacement.
- The existing RECON tab and its 4 sections (`#across`, `#active-runs`, `#recent-signals`, `#programs`) — they get wrapped in `<div id="tab-recon">` but their logic and layout are untouched.
- `aggregator.py`, `aggregator_blocks.py`, `dashboard.js`, `render.js`, `render_panels.js`, `dashboard.css`, `panels.css`, `tokens.css` — untouched.
- `providers.py`, `providers_openai_compat.py` — untouched. The per-task routing already exists via `complete(..., task=...)` → OpenRouter path → `resolve_model(task)`.

## Sources

This spec preserves the *ideas and solutions* of the REVISED plan at `docs/superpowers/plans/LLM-LOOP/PROBE-LIVE-TAB-REVISED/` (live tab, per-turn model selection, pentesting-aware prompt, structured SSE event payloads, frontend timeline) while adapting the *surfaces* to this project's conventions per the original plan at `docs/superpowers/plans/PROBE-LIVE-TAB.md` (stdlib server, real `earn_money` components, env-var-driven model selection, 200-line cap, `location.hash` tab state, `textContent`-only rendering).

The mapping was reviewed by `cursor-agent` ask-mode; the 7 issues raised in that review are addressed in this spec (see specific files for the resolution of each).

## Reading order

| #  | File                                                | Concern                                      |
|----|-----------------------------------------------------|----------------------------------------------|
| 00 | [00-overview.md](00-overview.md)                    | This file — goal, scope, what changes        |
| 01 | [01-architecture.md](01-architecture.md)            | Block diagram, threading, SSE framing        |
| 02 | [02-hacker-loop-hooks.md](02-hacker-loop-hooks.md)  | 6 new no-op hooks + safety-prompt update     |
| 03 | [03-task-routing.md](03-task-routing.md)            | `AGENT_PLANNING` TaskType + per-turn rule    |
| 04 | [04-robust-action-parsing.md](04-robust-action-parsing.md) | Markdown-fence stripping + `response_format` |
| 05 | [05-probe-runner.md](05-probe-runner.md)            | `ProbeRunner` contract, internals, lifecycle |
| 06 | [06-server-routes.md](06-server-routes.md)          | `POST /api/probe/start`, `GET /api/probe/stream` |
| 07 | [07-sse-contract.md](07-sse-contract.md)            | SSE event payloads, stage values, versioning |
| 08 | [08-frontend-html-tabs.md](08-frontend-html-tabs.md) | `index.html` tabs + `tabs.js`               |
| 09 | [09-frontend-probe-client.md](09-frontend-probe-client.md) | `probe.js` (SSE client) + `probe-render.js` |
| 10 | [10-frontend-css.md](10-frontend-css.md)            | `probe.css` + accessibility pairings         |
| 11 | [11-safety-gates.md](11-safety-gates.md)            | Hard / soft rules, failure-mode table        |
| 12 | [12-tests.md](12-tests.md)                          | Unit tests + manual smoke + coverage targets |
| 13 | [13-out-of-scope.md](13-out-of-scope.md)            | Deferred / rejected items, with triggers     |

## Phasing

Single phase. One sequenced PR. Implementation order is captured in the plan that follows this spec — `superpowers:writing-plans` is the next step.
