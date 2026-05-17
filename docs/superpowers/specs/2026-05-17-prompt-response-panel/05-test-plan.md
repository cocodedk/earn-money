# Test Plan

## Automated

### `tests/agent/test_hacker_loop.py`

Add a `TestPromptHook` class:

- `test_on_llm_response_called_with_prompt_and_system_on_first_call` — runs a one-turn loop with a valid stop action; asserts the hook was called once with `attempt=1`, `used_response_format=True`, `prompt` equal to `_build_prompt()` output, and `system` equal to `_SYSTEM_PROMPT`.
- `test_on_llm_response_called_twice_on_parse_retry` — primes the provider to return garbage then valid JSON; asserts hook called twice with `attempt=1` then `attempt=2`, with `used_response_format` flipping `True → False` and the same `prompt`/`system` values both times.
- `test_on_llm_response_attempt_2_only_when_retry_fires` — valid JSON on first call; asserts hook called once (no second call).
- `test_on_llm_response_attempt_1_used_response_format_false_when_provider_rejects_rf` — provider's first call (with `response_format`) raises; helper internally falls back without `response_format` and succeeds. Asserts the hook is called ONCE with `attempt=1, used_response_format=False` — proves the value flows end-to-end (helper → wrapper → hook) when the fallback happens inside a single `_get_llm_response` call.

Add a `TestProviderHelper` class — these target `_call_provider_with_rf_fallback` directly, not through `run()`. The point is to prove `used_response_format` reflects what the helper actually sent, decoupled from attempt number:

- `test_helper_returns_used_response_format_true_when_rf_succeeds` — `with_response_format=True`, provider returns valid JSON; helper returns `(raw, True)`.
- `test_helper_returns_used_response_format_false_when_caller_passes_false` — `with_response_format=False`, provider returns valid JSON; helper returns `(raw, False)`. Proves the field is per-call truth, not derived from attempt number. The helper already accepts `with_response_format=False` as a kwarg.
- `test_helper_returns_used_response_format_false_when_rf_call_raises` — `with_response_format=True`, first provider call raises (simulating provider rejection of `response_format`); helper falls back to a second call without rf and returns `(raw, False)`.

Add a `TestAttemptIdentity` class:

- `test_on_action_parsed_carries_attempt_1_when_first_call_parses` — happy path; asserts `_on_action_parsed` is called with `attempt=1`.
- `test_on_action_parsed_carries_attempt_2_when_retry_recovers` — garbage then valid; asserts `_on_action_parsed` is called with `attempt=2, parse_recovered=True`.
- `test_on_action_parse_failed_called_with_attempt_1_when_first_attempt_fails` — garbage then valid; asserts `_on_action_parse_failed` is called once with `attempt=1` and a non-empty `error` string.
- `test_on_action_parse_failed_called_twice_when_both_attempts_fail` — garbage on both calls; asserts `_on_action_parse_failed` called twice, with `attempt=1` then `attempt=2`.
- `test_no_action_parse_failed_on_happy_path` — valid on first call; asserts `_on_action_parse_failed` was never called.

Any existing test that constructs a `_on_action_parsed` callback with a positional signature must be updated to absorb the new `attempt` kwarg (`lambda *_a, **_k: …` works without changes).

### `tests/dashboard/test_probe_runner.py`

Add a `TestPromptInSseEvent` class:

- `test_action_pending_event_includes_full_prompt_and_system_with_long_raw` — drives one turn where the provider returns a **>250-char raw response** (e.g., `'{"tool":"stop","category":"stop","args":{"reason":"' + "x" * 250 + '"}}'`); drains queue; asserts:
    - `data["prompt"]` is non-empty
    - `data["system"]` is non-empty
    - `data["raw"] == full_raw` (exact equality; no truncation)
    - `data["raw_excerpt"] == full_raw[:200]`
    - `len(data["raw"]) > len(data["raw_excerpt"])` — guards against the case where a short mocked response would make truncation a no-op and falsely "pass" the test.
- `test_action_pending_event_includes_attempt_and_used_response_format` — asserts both new fields present with `attempt=1, used_response_format=True` for a single-attempt turn.
- `test_action_pending_event_emitted_twice_when_retry_fires` — primes provider with garbage then valid; asserts two `action_pending` events with `turn=1`, first `attempt=1, used_response_format=True`, second `attempt=2, used_response_format=False`.
- `test_action_pending_event_carries_used_response_format_false_when_provider_rejects_rf` — provider's first call raises; helper falls back internally. Asserts a SINGLE `action_pending` event for the turn with `attempt=1, used_response_format=False` — proves the value reaches the SSE wire, not just the hook.
- `test_raw_excerpt_still_present_for_backcompat` — asserts the existing `raw_excerpt` field is still in the event (200-char cap unchanged).

Add a `TestAttemptIdentityInSseEvent` class:

- `test_action_parsed_event_carries_attempt` — happy path; asserts the `action_parsed` event's `data` dict contains `attempt=1`.
- `test_action_parsed_event_carries_attempt_2_after_retry` — garbage then valid; asserts `action_parsed` event carries `attempt=2, parse_recovered=True`.
- `test_action_parse_failed_event_emitted_on_first_failure` — garbage then valid; asserts a `turn/action_parse_failed` event is emitted with `attempt=1` and a non-empty `error`, ordered between the two `action_pending` events.
- `test_action_parse_failed_event_not_emitted_on_happy_path` — valid on first call; asserts no `action_parse_failed` event in the stream.

### `tests/dashboard/test_probe_routes.py`

In the existing `TestStaticAssets` (or equivalent) class:

- `test_serves_probe_status_js` — `GET /static/probe-status.js` → 200 + `application/javascript`.
- `test_serves_probe_state_js` — `GET /static/probe-state.js` → 200 + `application/javascript`.
- `test_serves_probe_detail_css` — `GET /static/probe-detail.css` → 200 + `text/css`.
- `test_serves_probe_detail_js` — `GET /static/probe-detail.js` → 200 + `application/javascript`.

### `tests/dashboard/test_probe_static_assets.py` (new file)

Three regex-based static-file assertions: no DOM-write sinks in `probe-detail.js`; `index.html` links `probe-detail.css`; `index.html` loads the five probe JS files in dependency order.

```python
from pathlib import Path
import re

_BASE = Path(__file__).resolve().parents[2] / "src" / "earn_money" / "dashboard" / "templates"
_STATIC = _BASE / "static"
_INDEX = _BASE / "index.html"

_FORBIDDEN = re.compile(
    r"\binnerHTML\b|\binsertAdjacentHTML\b|\bouterHTML\b"
    r"|\bdocument\.write\b|\bcreateContextualFragment\b"
)

_EXPECTED_SCRIPT_ORDER = [
    "/static/probe-status.js",
    "/static/probe-state.js",
    "/static/probe-render.js",
    "/static/probe-detail.js",
    "/static/probe.js",
]


def test_probe_detail_js_uses_no_html_sinks():
    """LLM-controlled strings must render via textContent only."""
    src = (_STATIC / "probe-detail.js").read_text(encoding="utf-8")
    matches = [
        (i + 1, line) for i, line in enumerate(src.splitlines())
        if _FORBIDDEN.search(line)
    ]
    assert not matches, (
        "probe-detail.js must not use HTML-write sinks "
        "(innerHTML, insertAdjacentHTML, outerHTML, document.write, "
        f"createContextualFragment) — found {len(matches)} occurrence(s): {matches}"
    )


def test_index_html_loads_probe_detail_css():
    """The new panel CSS must be linked in index.html, or the panel ships unstyled."""
    html = _INDEX.read_text(encoding="utf-8")
    assert '"/static/probe-detail.css"' in html, (
        "index.html must <link> to /static/probe-detail.css"
    )


def test_index_html_loads_probe_scripts_in_dependency_order():
    """probe-status.js must load before probe-state.js, before the renderers, before probe.js."""
    html = _INDEX.read_text(encoding="utf-8")
    found = re.findall(r'<script[^>]+src="(/static/probe[^"]+\.js)"', html)
    assert found == _EXPECTED_SCRIPT_ORDER, (
        f"index.html script order must be {_EXPECTED_SCRIPT_ORDER}, got {found}"
    )
```

All three run in the regular `pytest` suite. Cannot be skipped.

**Author note on the HTML-sink test:** the regex matches raw bytes, including comments. Do not mention any of the forbidden sink names in `probe-detail.js` comments — the test will fail. Phrase comments as "use `textContent`" or "no DOM-write methods" instead. The strictness is deliberate.

### `tests/frontend/probe_state.test.mjs` + `tests/frontend/test_probe_state_runner.py` (new)

Tests the **shipped JS** — both `probe-state.js` (the reducer) and `probe-status.js` (the two helpers). Runs via Node's built-in test runner (`node --test`, no new deps for Node 18+). A tiny pytest wrapper invokes Node as a subprocess and surfaces failures; if `node` is not on PATH the wrapper skips with a clear message.

Pytest wrapper (`test_probe_state_runner.py`):

```python
import shutil, subprocess
import pytest

def test_probe_state_js_suite():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH — install Node 18+ to run the JS test suite")
    result = subprocess.run(
        [node, "--test", "tests/frontend/probe_state.test.mjs"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
```

`probe_state.test.mjs` cases (each `test()` block in the file):

**`probeReducer` — attempt matching:**
- `action_pending` for turn 1 attempt 1 → state.turns[1].attempts has one entry with `parseOutcome="pending"`.
- `action_parse_failed` for turn 1 attempt 1 → that attempt becomes `failed` with `parseError` set; no second attempt created.
- Subsequent `action_pending` for turn 1 attempt 2 → second attempt appended as `pending`; first attempt unchanged.
- `action_parsed` for turn 1 attempt 2 → only attempt 2 flips to `ok`; attempt 1 stays `failed`.
- `getTurnStatus(state.turns[1])` after the above sequence returns `"recovered"`.

**`probeReducer` — selection / follow-latest:**
- `setSelectedTurn(2)` sets `state.selectedTurn=2` AND `state.followLatest=false`.
- After `setSelectedTurn(2)`, a new `action_pending` for turn 3 does NOT change `selectedTurn`.
- `setFollowLatest(true)` re-enables auto-follow and re-selects the latest turn.

**`probeReducer` — run-level:**
- `probe_error` event sets `state.runError` and does NOT change any `state.turns[N]` field.
- `probe_start` event clears `state.turns`, `state.selectedTurn`, `state.runError`; resets `state.followLatest=true`.

**`probeReducer` — robustness:**
- Event with unknown `stage` is ignored silently (no exception, no state change).
- `onChange` callback fires exactly once per accepted event.

**`getTurnStatus` priority + `formatTurnStatus`:**
- Null turn → `"in_progress"`.
- Pending attempts + `complete=false` → `"in_progress"`.
- Single `ok` attempt + `complete=true` → `"ok"`.
- One `failed` then one `ok` → `"recovered"`.
- All `failed` → `"parse_failed"`.
- One `ok` + `policyDecision.allowed=false` → `"policy_blocked"` (priority beats `"ok"`).
- One `failed` + one `ok` + `policyDecision.allowed=false` → `"policy_blocked"` (priority beats `"recovered"`).
- `formatTurnStatus("recovered") === "invalid_action → recovered"` (and one assertion per enum value).

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

1. **Turn 1 lands.** Right panel auto-selects turn 1; header shows model + status text (initially `"in_progress"`, then the final status from `formatTurnStatus()` — e.g. `"ok"` or `"recovered"`). Delta tab shows the prompt's Session State block; Full tab shows the verbatim prompt. Response card shows the parsed action (or, for qwen, the retry pair).
2. **Turn 2 with retry.** Click turn 2 in the timeline (or let auto-follow do it). Two attempt cards stacked: `#1 with response_format` with warning border and `"encoding=UTF-8"` response; `#2 without response_format` with default border and the parsed `{"tool":"get",…}`.
3. **Tab switching.** Toggle between Delta and Full while on turn 2 — Full shows the entire prompt; Delta shows only the new Session State (the previous turn's observation appears as new context).
4. **Selection sticks.** Click turn 1, wait for turn 3 to arrive — panel stays on turn 1 and the `↓ follow latest` button appears.
5. **Follow-latest resumes.** Click `↓ follow latest` — panel jumps to turn 3.
6. **After done.** Probe completes; transcript stays visible; can still click any turn and toggle tabs.
7. **Restart.** Start a new probe — transcript clears, follow-latest re-engages.

## Security regression check

Covered by `tests/dashboard/test_probe_static_assets.py::test_probe_detail_js_uses_no_html_sinks` (see above). Pytest-level — cannot be skipped.
