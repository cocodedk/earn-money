# Task 1 — Add `AGENT_PLANNING` to `task_router.py`

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/03-task-routing.md` §1, §5, §7

**Files:**
- Modify: `src/earn_money/agent/task_router.py`
- Modify: `tests/agent/test_task_router.py`

The probe loop today passes `task="agent_planning"`; `coerce_task` doesn't know that string and collapses it to `DEFAULT_ASSISTANT`. Adding the enum value and its env-var mapping is the smallest correct fix.

- [ ] **Step 1: Write the failing test for `coerce_task`**

Append to `tests/agent/test_task_router.py`:

```python
def test_coerce_task_agent_planning():
    from earn_money.agent.task_router import TaskType, coerce_task
    assert coerce_task("agent_planning") == TaskType.AGENT_PLANNING
```

- [ ] **Step 2: Run the test — expect FAIL**

```bash
uv run pytest tests/agent/test_task_router.py::test_coerce_task_agent_planning -v
```

Expected: failure citing `AttributeError: type object 'TaskType' has no attribute 'AGENT_PLANNING'` (or the equivalent enum-value error from pydantic/Enum).

- [ ] **Step 3: Add the enum value + env mapping**

Edit `src/earn_money/agent/task_router.py`:

```python
class TaskType(StrEnum):
    """Spec §4 task taxonomy. New values must be added to `_PROFILE_ENV`."""

    DEFAULT_ASSISTANT = "default_assistant"
    CODING_SECURITY = "coding_security"
    REPORT_WRITING = "report_writing"
    STRUCTURED_EXTRACTION = "structured_extraction"
    DEEP_REASONING = "deep_reasoning"
    AGENT_PLANNING = "agent_planning"


_PROFILE_ENV: dict[TaskType, str] = {
    TaskType.DEFAULT_ASSISTANT:     "OPENROUTER_MODEL_DEFAULT_ASSISTANT",
    TaskType.CODING_SECURITY:       "OPENROUTER_MODEL_CODING_SECURITY",
    TaskType.REPORT_WRITING:        "OPENROUTER_MODEL_REPORT_WRITING",
    TaskType.STRUCTURED_EXTRACTION: "OPENROUTER_MODEL_STRUCTURED_EXTRACTION",
    TaskType.DEEP_REASONING:        "OPENROUTER_MODEL_DEEP_REASONING",
    TaskType.AGENT_PLANNING:        "OPENROUTER_MODEL_AGENT_PLANNING",
}
```

- [ ] **Step 4: Run the test — expect PASS**

```bash
uv run pytest tests/agent/test_task_router.py::test_coerce_task_agent_planning -v
```

- [ ] **Step 5: Add `resolve_model` coverage**

```python
def test_resolve_model_reads_agent_planning_env(monkeypatch):
    from earn_money.agent.task_router import resolve_model
    monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "qwen/qwen3-235b-a22b")
    assert resolve_model("agent_planning") == "qwen/qwen3-235b-a22b"


def test_resolve_model_falls_back_to_global_default(monkeypatch):
    from earn_money.agent.task_router import resolve_model
    monkeypatch.delenv("OPENROUTER_MODEL_AGENT_PLANNING", raising=False)
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "mistralai/mistral-small")
    assert resolve_model("agent_planning") == "mistralai/mistral-small"
```

- [ ] **Step 6: Run the new tests — expect PASS**

```bash
uv run pytest tests/agent/test_task_router.py -k agent_planning -v
```

- [ ] **Step 7: Run the full task-router test file to confirm no regression**

```bash
uv run pytest tests/agent/test_task_router.py -v
```

- [ ] **Step 8: Lint**

```bash
uv run ruff check src/earn_money/agent/task_router.py tests/agent/test_task_router.py
```

- [ ] **Step 9: Commit**

```bash
git add src/earn_money/agent/task_router.py tests/agent/test_task_router.py
git commit -m "feat(task-router): add AGENT_PLANNING task type"
```
