# Task 2 — `parse_action_with_recovery`

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/04-robust-action-parsing.md`

**Files:**
- Modify: `src/earn_money/agent/probe_actions.py`
- Modify: `tests/agent/test_probe_actions.py`

Reasoning-tuned models often return JSON wrapped in markdown fences or trailing prose. The current `parse_action` does `json.loads` directly and dies on `\`\`\`json … \`\`\``. We add a new `parse_action_with_recovery(raw) -> (ProbeAction, bool)` with three recovery layers, and keep `parse_action(raw) -> ProbeAction` as a back-compat wrapper.

- [ ] **Step 1: Write the first failing recovery test**

Append to `tests/agent/test_probe_actions.py`:

```python
class TestParseActionRecovery:
    def test_strips_json_fence(self):
        from earn_money.agent.probe_actions import (
            StopAction, parse_action_with_recovery,
        )
        raw = "```json\n{\"tool\":\"stop\",\"category\":\"stop\",\"args\":{}}\n```"
        action, recovered = parse_action_with_recovery(raw)
        assert isinstance(action, StopAction)
        assert recovered is True
```

- [ ] **Step 2: Run the test — expect FAIL (ImportError)**

```bash
uv run pytest tests/agent/test_probe_actions.py::TestParseActionRecovery::test_strips_json_fence -v
```

- [ ] **Step 3: Implement `parse_action_with_recovery` + keep `parse_action` as wrapper**

Edit `src/earn_money/agent/probe_actions.py`. Add the regex constant near the top imports:

```python
import re

_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(?P<body>.*?)\n?\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)
```

Replace the existing `parse_action` block (lines 123–143) with:

```python
def _try_load(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


_ParsedAction = (
    GetAction | PostAction | SetHeaderAction
    | StoreAction | ReportCandidateAction | StopAction
)


def parse_action_with_recovery(raw: str) -> tuple[_ParsedAction, bool]:
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
    return action, recovered  # type: ignore[return-value]


def parse_action(raw: str) -> _ParsedAction:
    """Existing API — preserved unchanged. Drops the recovery flag."""
    action, _ = parse_action_with_recovery(raw)
    return action
```

- [ ] **Step 4: Run the test — expect PASS**

```bash
uv run pytest tests/agent/test_probe_actions.py::TestParseActionRecovery::test_strips_json_fence -v
```

- [ ] **Step 5: Add the remaining recovery tests**

Append to the same class:

```python
    def test_strips_plain_fence_without_language_tag(self):
        from earn_money.agent.probe_actions import (
            StopAction, parse_action_with_recovery,
        )
        raw = "```\n{\"tool\":\"stop\",\"category\":\"stop\",\"args\":{}}\n```"
        action, recovered = parse_action_with_recovery(raw)
        assert isinstance(action, StopAction)
        assert recovered is True

    def test_extracts_json_from_prose_wrapping(self):
        from earn_money.agent.probe_actions import (
            StopAction, parse_action_with_recovery,
        )
        raw = 'Here is the action: {"tool":"stop","category":"stop","args":{}} done.'
        action, recovered = parse_action_with_recovery(raw)
        assert isinstance(action, StopAction)
        assert recovered is True

    def test_raises_when_no_json_object_present(self):
        import pytest
        from earn_money.agent.probe_actions import (
            ActionParseError, parse_action_with_recovery,
        )
        with pytest.raises(ActionParseError):
            parse_action_with_recovery("there is no json here at all")

    def test_recovered_flag_false_on_happy_path(self):
        from earn_money.agent.probe_actions import (
            StopAction, parse_action_with_recovery,
        )
        action, recovered = parse_action_with_recovery(
            '{"tool":"stop","category":"stop","args":{}}'
        )
        assert isinstance(action, StopAction)
        assert recovered is False


class TestParseActionBackwardCompat:
    def test_parse_action_still_returns_single_value(self):
        from earn_money.agent.probe_actions import StopAction, parse_action
        a = parse_action('{"tool":"stop","category":"stop","args":{}}')
        assert isinstance(a, StopAction)

    def test_parse_action_propagates_recovery_silently(self):
        from earn_money.agent.probe_actions import StopAction, parse_action
        raw = "```json\n{\"tool\":\"stop\",\"category\":\"stop\",\"args\":{}}\n```"
        a = parse_action(raw)
        assert isinstance(a, StopAction)
```

- [ ] **Step 6: Run the full probe-actions test file — expect all PASS, no regressions**

```bash
uv run pytest tests/agent/test_probe_actions.py -v
```

- [ ] **Step 7: Lint**

```bash
uv run ruff check src/earn_money/agent/probe_actions.py tests/agent/test_probe_actions.py
```

- [ ] **Step 8: Commit**

```bash
git add src/earn_money/agent/probe_actions.py tests/agent/test_probe_actions.py
git commit -m "feat(probe-actions): defensive parse_action_with_recovery + back-compat wrapper"
```
