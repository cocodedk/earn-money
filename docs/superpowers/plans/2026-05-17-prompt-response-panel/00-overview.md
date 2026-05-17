# Prompt & Response Detail Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement task-by-task. Per-task workflow is strict TDD: failing test → minimal impl → green test → commit → `/simplify` → commit (if simplify produced changes) → next task.

**Goal:** Surface the full prompt + raw LLM response per turn on the Probe Live Tab, with attempt-aware parse status, run-level error banner, and Delta/Full sub-tabs. Spec: `docs/superpowers/specs/2026-05-17-prompt-response-panel/consolidated.v6.md`.

**Architecture:** Server emits new fields on `turn/action_pending` plus `attempt` on `turn/action_parsed` plus a new `turn/action_parse_failed` event. Browser splits responsibilities into `probe-status.js` (pure helpers), `probe-state.js` (sole state writer + reducer), `probe-render.js` / `probe-detail.js` (read-only renderers), `probe.js` (DOM events, no state access).

**Tech Stack:** Python 3.12+ / pytest / mypy --strict (backend); plain JS via `<script>` tags / Node 22+ `--test --experimental-test-coverage` (frontend). No new deps.

**Coverage target:** 100% on every file touched by this feature. Backend via `pytest --cov`; frontend via `node --test --experimental-test-coverage` (or `c8` if Node <22). Coverage gap → block the task.

---

## Task list (TDD-ordered)

Execute in this order. Each task ends in: green test suite, commit, `/simplify` on changed files, commit-if-simplify-found-issues. Then move on.

### Backend (`01-backend.md`)

1. **B1.** Helper-direct tests for `_call_provider_with_rf_fallback` (`TestProviderHelper`). Pure addition — no production change. Verifies the existing tuple return contract that everything else depends on.
2. **B2.** Refactor `_get_llm_response` to return `(raw, used_response_format)` tuple; update call sites in `run()` to consume the tuple.
3. **B3.** Extend `_on_llm_response` signature with `*, system, prompt, attempt, used_response_format`. Pass through from `run()`. Add `TestPromptHook` tests.
4. **B4.** Extend `_on_action_parsed` signature with `*, attempt`. Add `TestAttemptIdentity` happy-path tests.
5. **B5.** New `_on_action_parse_failed(turn, attempt, error)` hook. Wire from `except ActionParseError` in `run()`. Complete `TestAttemptIdentity` failure-path tests.
6. **B6.** `ProbeRunner._on_llm_response` override: emit `system`, `prompt`, `raw`, `attempt`, `used_response_format` on `action_pending` event. Add `TestPromptInSseEvent` tests including the >250-char raw assertion.
7. **B7.** `ProbeRunner._on_action_parsed` override: emit `attempt`. Add corresponding SSE tests.
8. **B8.** `ProbeRunner._on_action_parse_failed` override: emit new `turn/action_parse_failed` SSE event. Complete SSE attempt-identity tests.

### Frontend (`02-frontend.md`)

9. **F1.** `probe-status.js` (≤60 lines) with `getTurnStatus()` and `formatTurnStatus()`. JS test infra (`tests/frontend/probe_status.test.mjs` + `tests/frontend/test_probe_state_runner.py`). All `getTurnStatus` priority cases.
10. **F2.** `probe-state.js` (≤160 lines): reducer, lifecycle helpers, `onChange`. Full reducer test cases (attempt matching, selection, follow-latest, run-level, robustness).
11. **F3.** `probe-detail.css` (≤150 lines): grid layout, sub-tabs, attempt cards, warning styling.
12. **F4.** `probe-detail.js` (≤170 lines): header, tabs, delta-diff (whitelist split + fallback), attempt-card builder. Calls `getTurnStatus` / `formatTurnStatus`. `textContent` only.
13. **F5.** Refactor `probe-render.js` to read-only — strip all state mutation; calls `getTurnStatus`/`formatTurnStatus`. Tests confirm timeline still renders.
14. **F6.** Refactor `probe.js` to no-state-access dispatcher. Wires EventSource → `probeReducer`, registers single `onChange` render trigger, fires `probe_start` on new probe.
15. **F7.** `index.html`: add `<aside id="probe-detail">`, `<link>` for `probe-detail.css`, five `<script>` tags in dependency order. Wire `.probe-body` grid container.
16. **F8.** Register four new static routes in `server.py::_STATIC_ROUTES`; add route smoke tests (`test_probe_routes.py`).
17. **F9.** `test_probe_static_assets.py` (three regex assertions: no DOM-write sinks, CSS link present, scripts in order).

### Verification (`03-coverage-and-e2e.md`)

18. **V1.** Run `pytest --cov=src/earn_money --cov-report=term-missing` against touched files; close every uncovered line.
19. **V2.** Run `node --test --experimental-test-coverage tests/frontend/`; close every uncovered line.
20. **V3.** Local smoke per `consolidated.v6.md § Manual verification § Pre-deploy local check`.
21. **V4.** Operator-driven VPS verification per `consolidated.v6.md § Live VPS check`.

---

## Conventions

- **One commit per task** (impl + tests together — they were authored together via TDD).
- **One `/simplify` per task** after the green commit. If simplify makes changes, commit those separately with `refactor:` prefix.
- **Pre-commit hook MUST pass** (ruff + mypy + pytest). Never `--no-verify`.
- **File size cap:** 200 lines per code/test/CSS/JS/HTML file. Split before exceeding.
- **Branch:** continue on `feat/run-target-script`. No new branch needed.
- **Commit prefix:** `feat(probe-panel):` for new behavior, `test(probe-panel):` for test-only commits, `refactor(probe-panel):` for /simplify follow-ups, `chore(probe-panel):` for HTML/CSS/static wiring.

## Plan files

- `00-overview.md` (this file)
- `01-backend.md` — tasks B1–B8 with code blocks
- `02-frontend.md` — tasks F1–F9 with code blocks
- `03-coverage-and-e2e.md` — tasks V1–V4
