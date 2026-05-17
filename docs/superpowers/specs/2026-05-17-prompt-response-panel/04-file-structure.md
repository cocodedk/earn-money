# File Structure & Line Budgets

Project rule: **200-line cap per code/test/HTML/CSS/JS file**. Splits below are pre-planned to stay within budget.

## Server (modify)

| File | Today | Change | After |
|------|-------|--------|-------|
| `src/earn_money/agent/hacker_loop.py` | 285 lines | Hook signature gains `*, prompt, attempt, used_response_format`; two `run()` call sites pass them | ~295 |
| `src/earn_money/dashboard/probe_runner.py` | 294 lines | Override emits new SSE fields; signature matches base | ~305 |

**Both files are already over the 200-line cap** (a pre-existing violation, not caused by this change). The additions here are surgical (≤15 lines each) and do not meaningfully worsen the violation. Splitting these two files into focused submodules is **explicit follow-up work** — out of scope for this branch. A separate spec / plan should:

- Extract `_call_provider_with_rf_fallback` and `_SYSTEM_PROMPT` from `hacker_loop.py` into `src/earn_money/agent/llm_call.py`.
- Split `probe_runner.py` into `probe_runner.py` (class + lifecycle) and `probe_runner_helpers.py` (module-level functions: `_augment_with_base_host`, `_apply_max_turns`, `_resolve_model_safely`, `_est_tokens`, `_summarise`).

Both extractions are mechanical; both are unrelated to the prompt-panel feature and would only inflate this change's risk surface.

## Frontend (modify)

| File | Today | Change | After |
|------|-------|--------|-------|
| `templates/index.html` | 83 lines | Add `<aside id="probe-detail">` skeleton; wrap timeline + aside in a `.probe-body` grid container | ~100 |
| `templates/static/probe.css` | 108 lines | Add grid wrapper + responsive collapse | ~140 |
| `templates/static/probe.js` | 84 lines | Add click handlers, tab toggle dispatch, follow-latest state | ~130 |
| `templates/static/probe-render.js` | 84 lines | Append each `action_pending` event to `state.turns[turn].attempts`; emit "turn updated" event | ~140 |

## Frontend (new)

| File | Lines (budget) | Purpose |
|------|----------------|---------|
| `templates/static/probe-detail.css` | ≤150 | Right panel layout: header, sub-tabs, attempt cards, warning border, prompt `<pre>` styling |
| `templates/static/probe-detail.js` | ≤170 | Right-panel renderer: header, tab switcher, delta-diff function, attempt-card builder. Reads from `state`, no DOM coupling to the timeline |

`probe-detail.js` is the most substantive new module. The delta-diff function (`splitPromptSections(prompt) → { sectionName: body }`, then compare two maps and keep only differing sections) is ~30 lines on its own.

## Server routes (modify)

`src/earn_money/dashboard/server.py` — `_STATIC_ROUTES` dict gains two entries:

```python
"/static/probe-detail.css": (_STATIC / "probe-detail.css", _CSS),
"/static/probe-detail.js":  (_STATIC / "probe-detail.js",  _JS),
```

No new HTTP route. No new handler method.

## Tests (modify + new)

| File | Change |
|------|--------|
| `tests/agent/test_hacker_loop.py` | Add tests asserting `_on_llm_response` is called with `prompt`, `attempt=1`, `used_response_format=True` on first call; with `attempt=2`, `used_response_format=False` on retry |
| `tests/dashboard/test_probe_runner.py` | Add tests asserting the SSE event for `action_pending` carries `prompt`, `raw` (full, not truncated), `attempt`, `used_response_format` |
| `tests/dashboard/test_probe_routes.py` | Register the two new static-asset paths; smoke-test 200 + Content-Type |

No frontend unit tests — consistent with the project today. Manual verification path is in `05-test-plan.md`.

## Files NOT touched

- `src/earn_money/agent/probe_actions.py` — parsing logic unchanged
- `src/earn_money/dashboard/templates/static/{tabs.js, render.js, render_panels.js, dashboard.js}` — recon-tab and shared-component code untouched
- `src/earn_money/dashboard/templates/static/{tokens.css, dashboard.css, panels.css}` — global styles untouched
- Any non-dashboard runner, ledger, or recon code

## Total impact

- 2 server files modified (lightly)
- 4 frontend files modified
- 2 frontend files added
- 3 test files modified
- 1 server route file modified (one-line additions)

Net additions: ~320 lines of new frontend code split across two files. No new dependencies. No new HTTP routes.
