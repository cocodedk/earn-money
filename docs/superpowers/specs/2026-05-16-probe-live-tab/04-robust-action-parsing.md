# 04 — Robust action parsing

Addresses the cursor-agent review concern about "loop dies on turn 1 when the model returns markdown-wrapped JSON." Two cheap defensive changes; no `supports_json_schema` registry, no per-task fallback chain.

## 1. The failure mode (verified)

`parse_action(raw: str)` in `src/earn_money/agent/probe_actions.py:123-143` does `json.loads(raw)` directly. The system prompt instructs the model to return raw JSON ("No prose. No markdown. No code blocks."), but reasoning-tuned models (DeepSeek R1, etc.) regularly violate that and return one of:

```
```json
{"tool":"get","category":"http_get","args":{"path":"/api/users"}}
```
```

or sometimes:

```
Here's the next action:
{"tool":"get",...}
```

The current code calls `json.loads("```json\n…")` → `JSONDecodeError` → `ActionParseError` → loop ends with `stop_reason="invalid_action"`. The probe live tab would surface this as a single error card on turn 1 — exactly the "failing miserably" the review warned about.

This is independent of the model's *capabilities*; it's a prompt-compliance issue. The same model can return clean JSON one call and fenced JSON the next.

## 2. Fix part A — fence-stripping fallback

Add a new `parse_action_with_recovery(raw)` that does the defensive parsing AND returns a `parse_recovered` flag. Keep `parse_action(raw)` as a thin wrapper that drops the flag — this preserves the existing single-return signature for the CLI (`hacker_loop_cli.py`) and the existing test suite without any callsite churn.

```python
_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(?P<body>.*?)\n?\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)

def _try_load(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_action_with_recovery(raw: str) -> tuple[ProbeAction, bool]:
    """Parse `raw` into a typed action. Returns `(action, parse_recovered)`
    where `parse_recovered` is True when the happy-path `json.loads` failed
    and one of the recovery layers had to fire."""
    data = _try_load(raw)
    recovered = False
    if data is None:
        recovered = True
        m = _FENCE_RE.match(raw)
        if m:
            data = _try_load(m.group("body"))
        if data is None:
            # Last resort: pull the first {...} substring. Bounded scan — if
            # the model wrote "Here's the action: {...} done", we still parse.
            i, j = raw.find("{"), raw.rfind("}")
            if 0 <= i < j:
                data = _try_load(raw[i : j + 1])
        if data is None:
            raise ActionParseError(f"Invalid JSON: could not parse {raw[:80]!r}")

    tool = data.get("tool")
    if not isinstance(tool, str) or tool not in _TOOL_MAP:
        raise ActionParseError(f"Unknown tool: {tool!r}")
    cls = _TOOL_MAP[tool]
    try:
        action = cls.model_validate(data)
    except Exception as e:
        raise ActionParseError(str(e)) from e
    return action, recovered


def parse_action(raw: str) -> ProbeAction:
    """Existing API — preserved unchanged. Drops the recovery flag."""
    action, _ = parse_action_with_recovery(raw)
    return action
```

Three recovery layers, all defensive, no API change for existing callers:

1. Direct `json.loads` — the happy path; works when the model obeys the prompt.
2. Fenced-block strip — works for ` ```json … ``` ` and ` ``` … ``` `.
3. First-curly-to-last-curly substring — works for prefixed/suffixed prose around a single JSON object.

If all three fail, raise — the action really is unparseable, and the loop should stop.

`HackerLoop.run()` calls `parse_action_with_recovery` (so the loop can pass `parse_recovered` to the `_on_action_parsed` hook). The CLI's existing call to `parse_action(raw)` is untouched.

## 3. Fix part B — best-effort `response_format` passthrough

`structured.py` already builds a `response_format = {"type": "json_schema", "json_schema": …}` payload, and `providers_openai_compat.py:96-97` already passes it to the OpenAI/OpenRouter SDK. The probe loop doesn't currently use this path. We change `HackerLoop._get_llm_response` to pass `response_format` as a best-effort cue:

```python
def _get_llm_response(self, prompt: str) -> str | None:
    try:
        return self.provider.complete(
            system=_SYSTEM_PROMPT,
            user=prompt,
            task="agent_planning",
            response_format=_ACTION_RESPONSE_FORMAT,   # ← new
        )
    except Exception as e:
        log.error("Provider error: %s", e)
        return None
```

`_ACTION_RESPONSE_FORMAT` is a module-level constant in `hacker_loop.py` pointing at the existing pydantic-derived schema (or a minimal hand-written one — the simplest viable schema is `{"type":"json_object"}`, which OpenRouter accepts for every model that supports any structured output and ignores otherwise).

**Decision: use the minimal `{"type":"json_object"}` form.** Reasons:

(Implementer note: `src/earn_money/agent/structured.py` already builds the full `{"type":"json_schema", ...}` form and is used by the decider. If a future iteration adds per-model `response_format` selection — schema-capable models get the rich form, others get `json_object`, others get nothing — that switching logic belongs in `structured.py` or a thin wrapper, not duplicated in the probe loop. Out of scope for this spec.)


- The full JSON-Schema variant (`{"type":"json_schema","json_schema":{…}}`) requires building the schema and is rejected by some OpenRouter models with a 400.
- The minimal `json_object` form is widely supported and tells the model "return valid JSON" without committing to a specific shape — which the system prompt and `parse_action` already enforce.
- Providers that don't support `response_format` at all (Anthropic, HuggingFace adapters in this repo) already ignore the kwarg per their own implementations (`providers.py:79-80`, `providers.py:111-112`).

Zero-cost on the bad path, helpful nudge on the good path.

## 4. Why not the proposed `supports_json_schema` registry

The reviewer suggested adding `supports_json_schema: bool` to a model-capabilities registry and a per-task fallback chain in `resolve_model()`. Rejected, with reasons:

- **No registry exists.** `model_scout.py` ranks free OpenRouter models against task profiles using substring + context-length heuristics — it has no capability flags. Building a registry means hand-maintaining a list of model IDs that goes stale weekly as OpenRouter rotates its catalogue.
- **Fallback chains hide bugs.** If `OPENROUTER_MODEL_DEEP_REASONING` silently re-routes to `OPENROUTER_MODEL_STRUCTURED_EXTRACTION`, the live tab will *show* "DeepSeek R1" being used in the SSE event but actually be using Qwen3. Operator confusion guaranteed.
- **Defensive parsing handles the real failure mode without the registry overhead.** The two fixes above cover markdown fences, prose-wrapping, and any provider that ignores `response_format` — the actual failure modes seen in practice.

If we observe in the live tab that one specific model consistently fails parse-recovery, the right move is to either (a) configure the env var to a different model, or (b) drop that model from `model_scout.py`'s rankings — not to grow a capability registry.

## 5. Tests

- `tests/agent/test_probe_actions.py` gets three new cases:
  - `parse_action` recovers from ` ```json\n{…}\n``` ` fences.
  - `parse_action` recovers from ` ```\n{…}\n``` ` (no language tag).
  - `parse_action` recovers from `"Here is the action: {…} done."` prose wrapping.
  - `parse_action` still raises for fully un-JSON strings (negative test).
- `tests/agent/test_hacker_loop.py` gets one case: the loop calls `provider.complete` with `response_format={"type":"json_object"}`. (Mocked provider; verifies the kwarg, doesn't exercise real OpenRouter.)

## 6. Visibility in the live tab

When recovery fires, the `parse_recovered` bool returned by `parse_action_with_recovery` is passed to `_on_action_parsed`, and `ProbeRunner` puts it into the SSE `turn` event at `stage="action_parsed"` (see [07-sse-contract.md](07-sse-contract.md)). The renderer shows a small ⚠ "recovered" prefix on the action slot so the operator can see *that* a recovery happened (and which model emitted the malformed output).

The hook timing is important: `parse_recovered` is **not** part of the `action_pending` event (which fires before parsing) — it lives on the new `action_parsed` event right after. See [02-hacker-loop-hooks.md](02-hacker-loop-hooks.md) §"Where the hooks fire" for the exact sequence.
