# 03 — Task routing

This is the smallest correct change that fixes the root cause REVISED was pointing at: every probe turn currently routes to `DEFAULT_ASSISTANT` because `coerce_task("agent_planning")` returns the default for an unknown string. We add **one** new `TaskType` and a per-turn selection rule in `ProbeRunner`.

## 1. New TaskType: `AGENT_PLANNING`

In `src/earn_money/agent/task_router.py`:

```python
class TaskType(StrEnum):
    DEFAULT_ASSISTANT = "default_assistant"
    CODING_SECURITY = "coding_security"
    REPORT_WRITING = "report_writing"
    STRUCTURED_EXTRACTION = "structured_extraction"
    DEEP_REASONING = "deep_reasoning"
    AGENT_PLANNING = "agent_planning"          # ← NEW

_PROFILE_ENV: dict[TaskType, str] = {
    TaskType.DEFAULT_ASSISTANT:     "OPENROUTER_MODEL_DEFAULT_ASSISTANT",
    TaskType.CODING_SECURITY:       "OPENROUTER_MODEL_CODING_SECURITY",
    TaskType.REPORT_WRITING:        "OPENROUTER_MODEL_REPORT_WRITING",
    TaskType.STRUCTURED_EXTRACTION: "OPENROUTER_MODEL_STRUCTURED_EXTRACTION",
    TaskType.DEEP_REASONING:        "OPENROUTER_MODEL_DEEP_REASONING",
    TaskType.AGENT_PLANNING:        "OPENROUTER_MODEL_AGENT_PLANNING",  # ← NEW
}
```

After this, `coerce_task("agent_planning")` returns `TaskType.AGENT_PLANNING` (string match against the enum value via `TaskType(value)`), and `resolve_model` reads `OPENROUTER_MODEL_AGENT_PLANNING` first, falling back to `OPENROUTER_DEFAULT_MODEL`. The fallback chain is unchanged; we're just adding one more profile.

## 2. Why only one new TaskType (not three)

The brainstorm initially proposed `AGENT_PLANNING + EXPLOIT_REASONING + EVIDENCE_SUMMARY`. The cursor-agent review flagged that `EVIDENCE_SUMMARY` had no routing site in the mapping; the same is true for `EXPLOIT_REASONING`. Adding TaskTypes that no code routes to is dead enum surface — it confuses future implementers and bloats `.env.example` without value. Both can land later, in their own focused changes, when there's a concrete routing site:

- `EVIDENCE_SUMMARY` — when a periodic "summarise last 5 observations" turn is added to the loop.
- `EXPLOIT_REASONING` — when a chain-validation turn is added (after the verifier promotes a candidate).

Today the loop has neither, so this spec adds neither.

## 3. Per-turn task selection (in `ProbeRunner`)

The base `HackerLoop._get_llm_response` always passes `task="agent_planning"`. With the new TaskType, that resolves consistently to one model — better than the status quo, but it doesn't yet give us the *per-turn intelligence* REVISED was after.

`ProbeRunner` overrides `_get_llm_response` to pick the task from observation/action context:

```python
def _get_llm_response(self, prompt: str) -> str | None:
    task = self._pick_task()
    self._last_model_id = _resolve_model_safely(task)
    try:
        return self.provider.complete(
            system=_SYSTEM_PROMPT, user=prompt, task=task,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        log.error("Provider error: %s", e)
        return None

def _pick_task(self) -> str:
    # Hint set by the previous turn (e.g. after report_candidate) wins.
    if self._next_task_hint:
        return self._next_task_hint

    if not self.session.observations:
        # Turn 1 — no observations yet. Stay on AGENT_PLANNING; do NOT use
        # DEEP_REASONING here even though it would give better strategic
        # framing. Reasoning models are JSON-hostile (chain-of-thought prose
        # before/after JSON) and every action turn MUST return a valid JSON
        # action. Save DEEP_REASONING for future non-action steps (planning /
        # summarisation) — see 13-out-of-scope.md §E.
        return "agent_planning"

    last = self.session.observations[-1]
    ctype = (last.headers.get("content-type") or "").lower()
    body = last.body or ""

    # Response body is code-like: route to the code analyser.
    if "javascript" in ctype:
        return "coding_security"
    if "text/html" in ctype and "<script" in body.lower():
        return "coding_security"

    # Default for ongoing probing: the agent planner.
    return "agent_planning"
```

There are two more selection sites, both in `_execute_action`-time decisions rather than in `_get_llm_response`. They cover *intent* (what the model is about to do):

- After the model has just emitted a `ReportCandidateAction`, the **next** turn benefits from `STRUCTURED_EXTRACTION` (the model is formatting a finding, not reasoning about HTTP). `ProbeRunner` carries `self._next_task_hint: str | None` set in `_on_turn_complete` when the just-completed action was `report_candidate`. `_pick_task` checks this hint and consumes it.
- After the model has emitted `StopAction`, no further LLM call happens — the loop exits. No special-casing needed.

Final mapping (resolves cursor-agent review #2 and the second reviewer's #10):

| Condition (evaluated at `_pick_task` time)              | Task                    |
|---------------------------------------------------------|-------------------------|
| `_next_task_hint == "structured_extraction"`            | `STRUCTURED_EXTRACTION` |
| Last obs Content-Type indicates JS/HTML+`<script>`      | `CODING_SECURITY`       |
| Otherwise (incl. turn 1 with no observations yet)       | `AGENT_PLANNING`        |

Three branches, no first-turn special case. Every action turn routes to a task profile whose conventional model choices honour JSON-only output. `DEEP_REASONING` is intentionally not in the action loop — it stays available for future non-action steps where prose is acceptable.

## 4. Resolving the model id for hook 1

`_resolve_model_safely(task)` in `ProbeRunner` calls `task_router.resolve_model(task)` and catches `RouterUnconfigured`, returning `None` (the hook accepts `None`). This lets the dashboard run even when the operator hasn't set every per-task env var — only `OPENROUTER_DEFAULT_MODEL` is strictly required, matching the existing convention.

## 5. `.env.example` addition

```
# Probe loop per-turn model selection (optional — falls back to OPENROUTER_DEFAULT_MODEL)
OPENROUTER_MODEL_AGENT_PLANNING=
```

The other four `OPENROUTER_MODEL_*` entries already exist; this is one new line.

## 6. Documentation in `task_router.py`

The docstring at the top of `task_router.py` is extended with one short paragraph listing suggested OpenRouter IDs per profile **as a comment, not as code**:

```
# Suggested OpenRouter IDs (operator-configurable, not enforced):
#   DEFAULT_ASSISTANT     → mistralai/mistral-small  or  qwen/qwen3-235b-a22b
#   AGENT_PLANNING        → qwen/qwen3-235b-a22b      (strong instruction following)
#   DEEP_REASONING        → deepseek/deepseek-r1     (chain-of-thought)
#   CODING_SECURITY       → qwen/qwen3-coder
#   STRUCTURED_EXTRACTION → qwen/qwen3-235b-a22b
#   REPORT_WRITING        → mistralai/mistral-small
```

Documentation only. The router stays purely env-var driven; no `PENTEST_MODEL_RECOMMENDATIONS` dict, no fallback logic baked in.

## 7. Tests

- `tests/agent/test_task_router.py` gains one case: `coerce_task("agent_planning") == TaskType.AGENT_PLANNING` and `resolve_model("agent_planning")` honours `OPENROUTER_MODEL_AGENT_PLANNING` then `OPENROUTER_DEFAULT_MODEL`.
- `tests/dashboard/test_probe_runner.py` (covered in detail in [12-tests.md](12-tests.md)) covers `_pick_task` for each of the three mapping branches plus the `report_candidate → STRUCTURED_EXTRACTION` hint.
