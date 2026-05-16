# Probe Live Tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second tab — **PROBE** — to the existing dashboard that lets the operator launch `probe-target` against any URL and watch the `HackerLoop` execute live (turn-by-turn, with per-step model/policy/observation/finding visibility) via Server-Sent Events.

**Architecture:** A daemon thread inside the stdlib `ThreadingHTTPServer` runs a `ProbeRunner` (subclass of `HackerLoop`) that overrides six no-op hooks added to the base loop, pushing structured events onto a `queue.Queue`. Two new routes (`POST /api/probe/start`, `GET /api/probe/stream?run_id=…`) gate the run with `RECON_ENABLED` / `FROZEN` and frame queue events as SSE for the browser. The CLI (`bin/probe-target`) is untouched; the dashboard is an alternate launcher.

**Tech Stack:** Python 3.12 · `http.server` stdlib · `threading.Thread` + `queue.Queue` · pydantic v2 actions · vanilla DOM + `EventSource` (no build step) · pytest.

**Source spec:** `docs/superpowers/specs/2026-05-16-probe-live-tab/` (14 files, signed off as implementation-ready).

---

## Pre-flight checks

Before starting Task 1, the engineer should confirm:

- `git status` is clean on branch `feat/run-target-script` (or its successor) — no uncommitted local edits.
- `uv run pytest -q` passes the existing suite (~795 tests).
- `uv run ruff check src/ tests/` is clean.
- `.env.example` may or may not exist at the repo root. Task 12 handles both cases: append if present, create with the single new line if absent. Do **not** copy keys from `.env` (it contains secrets).

## File map

| Action | Path | Concern |
|--------|------|---------|
| Modify | `src/earn_money/agent/task_router.py` | Add `AGENT_PLANNING` TaskType + env entry |
| Modify | `src/earn_money/agent/probe_actions.py` | Add `parse_action_with_recovery`; keep `parse_action` as wrapper |
| Modify | `src/earn_money/agent/hacker_loop.py` | 6 no-op hooks + `_current_turn`/`_last_model_id` init + augmented `_SYSTEM_PROMPT` + `response_format` passthrough + use `parse_action_with_recovery` |
| Create | `src/earn_money/dashboard/probe_runner.py` | `ProbeRunner(HackerLoop)` — hook overrides, queue emit, lifecycle |
| Modify | `src/earn_money/dashboard/server.py` | `_PROBE_SLOT` + lock + `_clear_probe_slot` + `_paths` class attr + two routes + dispatcher + new static routes |
| Modify | `src/earn_money/dashboard/templates/index.html` | Tab bar, wrap RECON sections, add PROBE section, CSS link in `<head>`, scripts at end-of-body |
| Create | `src/earn_money/dashboard/templates/static/tabs.js` | Pure client-side tab switching (`location.hash`) |
| Create | `src/earn_money/dashboard/templates/static/probe.js` | Form submit + `EventSource` driver + `state.closed` guard |
| Create | `src/earn_money/dashboard/templates/static/probe-render.js` | DOM renderers exposed as `window.ProbeRender` |
| Create | `src/earn_money/dashboard/templates/static/probe.css` | Timeline / turn-card / badge styles |
| Modify | `.env.example` (or create) | `OPENROUTER_MODEL_AGENT_PLANNING=` line |
| Modify | `tests/agent/test_task_router.py` | `AGENT_PLANNING` coverage |
| Modify | `tests/agent/test_probe_actions.py` | Recovery cases + back-compat |
| Modify | `tests/agent/test_hacker_loop.py` | Hook ordering + `response_format` passthrough |
| Create | `tests/dashboard/test_probe_runner.py` | Hooks, `_pick_task`, lifecycle |
| Create | `tests/dashboard/test_probe_routes.py` | Both routes, validation, SSE framing |

## Task order (each task lives in its own file)

| # | File | Touches |
|---|------|---------|
| 1 | [01-task-router-agent-planning.md](01-task-router-agent-planning.md) | `task_router.py` + test |
| 2 | [02-parse-action-recovery.md](02-parse-action-recovery.md) | `probe_actions.py` + test |
| 3 | [03-hacker-loop-changes.md](03-hacker-loop-changes.md) | `hacker_loop.py` + test |
| 4 | [04-probe-runner-class.md](04-probe-runner-class.md) | `probe_runner.py` + test |
| 5 | [05-server-slot-and-paths.md](05-server-slot-and-paths.md) | `server.py` state + handler attr |
| 6 | [06-server-start-route.md](06-server-start-route.md) | `POST /api/probe/start` + tests |
| 7 | [07-server-stream-route.md](07-server-stream-route.md) | `GET /api/probe/stream` + tests |
| 8 | [08-server-dispatch-and-static.md](08-server-dispatch-and-static.md) | `do_GET`/`do_POST` + new static routes |
| 9 | [09-frontend-html-tabs.md](09-frontend-html-tabs.md) | `index.html` + `tabs.js` |
| 10 | [10-frontend-probe-client.md](10-frontend-probe-client.md) | `probe.js` + `probe-render.js` |
| 11 | [11-frontend-css.md](11-frontend-css.md) | `probe.css` |
| 12 | [12-env-and-final-pass.md](12-env-and-final-pass.md) | `.env.example` + full test+lint pass |

## Conventions for every task

1. **TDD** — write the failing test first, run it, watch it fail with the expected message, then implement, run again, watch it pass, then commit.
2. **One commit per task** — Conventional Commits prefix (`feat:`, `fix:`, `chore:`, `test:`, `refactor:`).
3. **Never `--no-verify`** — pre-commit hooks are the floor.
4. **No invented scope** — every line of code in a step is either copied verbatim from the source spec or derived directly from a spec snippet. If a step needs something the spec doesn't describe, stop and ask.
5. **Surgical changes** — modify only the lines a task targets. Match existing style; don't re-format adjacent code.
6. **File size — readability guidance, not a merge blocker.** Keep files readable. Split when a file becomes hard to understand or mixes unrelated responsibilities. Line count alone is not a gate. (The earlier draft of this plan had a hard 200/150 cap; downgraded to guidance after reviewer feedback that some prescribed code legitimately runs past the cap and that splitting just to hit a number degrades clarity.)
