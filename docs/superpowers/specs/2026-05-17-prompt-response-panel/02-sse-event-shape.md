# SSE Event Shape

Three event shapes change:

1. `turn/action_pending` — gains new fields (prompt, system, raw, attempt, used_response_format)
2. `turn/action_parsed` — gains `attempt`
3. `turn/action_parse_failed` — **new event**, fires on every failed parse

Other event types (`turn/policy`, `turn/observation`, `turn/complete`, `finding`, `done`, `probe_error`, `_keepalive`) are unchanged.

## `turn/action_pending`

### Today

```json
{
  "event": "turn",
  "data": {
    "turn": 2,
    "stage": "action_pending",
    "model": "qwen/qwen3-235b-a22b",
    "raw_excerpt": "{",
    "estimated_tokens": 0
  }
}
```

### New

```json
{
  "event": "turn",
  "data": {
    "turn": 2,
    "stage": "action_pending",
    "model": "qwen/qwen3-235b-a22b",
    "attempt": 1,
    "used_response_format": true,
    "system": "You are assisting with authorized security testing.\n…",
    "prompt": "=== Rules of Engagement ===\n…",
    "raw": "{",
    "raw_excerpt": "{",
    "estimated_tokens": 0
  }
}
```

### Field semantics

| Field | Type | Notes |
|-------|------|-------|
| `attempt` | int | Call ordinal within this turn, 1-indexed. In current code reaches at most 2 (retry-without-`response_format`); field is open-ended for future expansion |
| `used_response_format` | bool | What THIS specific call actually sent to the provider. Read from the helper's return value; never derived from `attempt`. An `attempt=1` event can carry `false` if the caller started with `with_response_format=false` (e.g., a future model-capability gate) |
| `system` | string | The exact `system=…` kwarg passed to `provider.complete()`. In current code this is the `_SYSTEM_PROMPT` module constant — same value every call. Emitted per-event for self-containment |
| `prompt` | string | The exact `user=…` kwarg passed to `provider.complete()`. Built by `_build_prompt()` — contains RoE + session view + action menu. **Does NOT include the system prompt** (that's the `system` field) |
| `raw` | string | Full untruncated raw LLM response. May be empty string if provider returned `None`/empty |
| `raw_excerpt` | string | **Kept for back-compat.** Still `raw[:200]` so the timeline renderer doesn't need changes |

**What's NOT in the payload (deliberately, for v1):** `temperature`, `max_tokens`, `response_format_type`, or any other provider kwargs. The current debugging goal only requires "did response_format go out, yes/no?" and the operator gets that from `used_response_format`. Broader request metadata is deferred until a concrete debugging need motivates it.

## `turn/action_parsed`

### Today

```json
{
  "event": "turn",
  "data": {
    "turn": 1,
    "stage": "action_parsed",
    "action": {"tool": "get", "category": "http_get", "args": {...}},
    "parse_recovered": false
  }
}
```

### New

```json
{
  "event": "turn",
  "data": {
    "turn": 1,
    "stage": "action_parsed",
    "attempt": 2,
    "action": {"tool": "get", "category": "http_get", "args": {...}},
    "parse_recovered": true
  }
}
```

`attempt` identifies which `action_pending` event's raw text actually parsed. The browser must NOT infer this from event ordering.

## `turn/action_parse_failed` (new)

Fires from inside the `except ActionParseError` block in `HackerLoop.run()`. One event per failed parse attempt.

```json
{
  "event": "turn",
  "data": {
    "turn": 1,
    "stage": "action_parse_failed",
    "attempt": 1,
    "error": "Expecting value: line 1 column 2 (char 1)"
  }
}
```

The frontend matches this event to the right attempt card via `(turn, attempt)` and flips its `parseOutcome` to `"failed"`.

### Retry case (the common qwen path)

A single turn with a parse-retry produces **four** events in order:

1. `action_pending` `attempt=1, used_response_format=true, raw="{"` (or whatever garbage)
2. `action_parse_failed` `attempt=1, error="..."`
3. `action_pending` `attempt=2, used_response_format=false, raw='{"tool":"get",…}'`
4. `action_parsed` `attempt=2, parse_recovered=true`

All four carry the same `turn` number. Happy path produces only events 1 and 4 (no failure event, `parse_recovered=false`).

### Size budget

- Typical `system`: 1–2 KB (constant)
- Typical `prompt`: 4–8 KB
- Typical `raw`: 80–200 bytes (it's one JSON action)
- Per `action_pending` event: ~6–11 KB
- Worst case per turn (assuming retry): 2 × 11 KB = ~22 KB

**Caveat — large-raw outliers.** A misbehaving model can emit much larger `raw` (thousands of tokens of garbage instead of one JSON object). The 22-KB number is "typical retry," not "worst case." Server makes no attempt to cap; values >100 KB stay full-fidelity over the wire. Soft policy:

- Server never truncates `prompt`, `system`, or `raw` — observability is the whole point of this feature.
- Client renders these in scrollable `<pre>` blocks; browser memory comfortably holds tens of MB.
- If a real-world run produces a `raw` so large it degrades the SSE stream or UI, that's a future-revision problem — add a "this field is 250 KB, click to expand" affordance, NOT a hard truncation.

### Security

All five LLM-controlled string fields (`system`, `prompt`, `raw`, `raw_excerpt`, `model`) MUST be rendered via `textContent` — never `innerHTML` / `insertAdjacentHTML` / `outerHTML` / `document.write` / `createContextualFragment`. `prompt` and `raw` carry target-supplied bytes (HTTP response bodies echoed in observations); `system` comes from a project constant. Enforced by `test_probe_detail_js_uses_no_html_sinks` (`05-test-plan.md`).

### Back-compat

The existing `raw_excerpt` and `estimated_tokens` fields are unchanged. An older browser tab connected to the new server receives extra fields and ignores them. A newer browser connected to an older server (no `attempt` on `action_parsed`, no `action_parse_failed` event) cannot correctly attribute parse status — the detail panel will show all attempts as `"pending"`. Acceptable degradation; both sides ship together.
