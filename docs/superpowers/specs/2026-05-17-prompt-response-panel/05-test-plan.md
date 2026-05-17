# Test Plan

## Automated

### `tests/agent/test_hacker_loop.py`

Add a `TestPromptHook` class:

- `test_on_llm_response_called_with_prompt_and_attempt_1_on_first_call` — runs a one-turn loop with a valid stop action; asserts the hook was called once with `attempt=1`, `used_response_format=True`, and `prompt` equal to the value returned by `_build_prompt()`.
- `test_on_llm_response_called_twice_on_parse_retry` — primes the provider to return garbage then valid JSON; asserts hook called twice with `attempt=1` then `attempt=2`, with `used_response_format` flipping `True → False` and the same `prompt` value both times.
- `test_on_llm_response_attempt_2_only_when_retry_fires` — provider returns valid JSON on first call; asserts hook called once with `attempt=1` (no second call).

Existing `TestHooks` tests use `lambda *_a, **_k: …` and should keep working without modification — new kwargs are absorbed by `**_k`.

### `tests/dashboard/test_probe_runner.py`

Add a `TestPromptInSseEvent` class:

- `test_action_pending_event_includes_full_prompt` — drives one turn; drains queue; asserts the `action_pending` event's `data` dict contains `prompt` (non-empty string) and `raw` (full response, not 200-char truncated).
- `test_action_pending_event_includes_attempt_and_used_response_format` — asserts both new fields present with `attempt=1, used_response_format=True` for a single-attempt turn.
- `test_action_pending_event_emitted_twice_when_retry_fires` — primes provider with garbage then valid; asserts two `action_pending` events with `turn=1`, first `attempt=1`, second `attempt=2`.
- `test_raw_excerpt_still_present_for_backcompat` — asserts the existing `raw_excerpt` field is still in the event (200-char cap unchanged).

### `tests/dashboard/test_probe_routes.py`

In the existing `TestStaticAssets` (or equivalent) class:

- `test_serves_probe_detail_css` — `GET /static/probe-detail.css` → 200 + `text/css`.
- `test_serves_probe_detail_js` — `GET /static/probe-detail.js` → 200 + `application/javascript`.

## Manual verification

### Pre-deploy local check

```bash
touch RECON_ENABLED
uv run python -m earn_money.dashboard.server --root . &
# open http://127.0.0.1:8080/, switch to Probe tab
# observe the split layout — left column = timeline, right column = empty "Waiting for first turn…" panel
```

### Live VPS check (the canonical verification)

After deploy, repeat the juice shop probe (`https://target.cocode.dk`, local_lab). Observe:

1. **Turn 1 lands.** Right panel auto-selects turn 1; header shows model + "in progress" then "complete". Delta tab shows the prompt's Session State block; Full tab shows the verbatim prompt. Response card shows the parsed action (or, for qwen, the retry pair).
2. **Turn 2 with retry.** Click turn 2 in the timeline (or let auto-follow do it). Two attempt cards stacked: `#1 with response_format` with warning border and `"encoding=UTF-8"` response; `#2 without response_format` with default border and the parsed `{"tool":"get",…}`.
3. **Tab switching.** Toggle between Delta and Full while on turn 2 — Full shows the entire prompt; Delta shows only the new Session State (the previous turn's observation appears as new context).
4. **Selection sticks.** Click turn 1, wait for turn 3 to arrive — panel stays on turn 1 and the `↓ follow latest` button appears.
5. **Follow-latest resumes.** Click `↓ follow latest` — panel jumps to turn 3.
6. **After done.** Probe completes; transcript stays visible; can still click any turn and toggle tabs.
7. **Restart.** Start a new probe — transcript clears, follow-latest re-engages.

## Security regression check

After deploy, manually verify no `innerHTML` usage in `probe-detail.js`:

```bash
grep -n "innerHTML\|insertAdjacentHTML" src/earn_money/dashboard/templates/static/probe-detail.js
# expected: no output
```

This is also catchable in code review and via the existing project lint config if it covers JS, but the dashboard JS is currently un-linted, so the manual grep is the safety net.
