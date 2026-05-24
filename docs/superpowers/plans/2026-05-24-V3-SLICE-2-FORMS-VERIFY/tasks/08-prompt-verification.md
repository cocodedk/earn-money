---
tier: FAST
depends_on:
  - 01-action-dataclasses
files:
  creates: []
  modifies:
    - backend/apps/agent/actions/matrix.py
    - backend/apps/agent/llm/prompts.py
    - backend/apps/agent/tests/test_prompts.py
  deletes: []
exports: []
imports:
  - FillFormAction
  - SubmitFormAction
allow_extra_files: false
---

### Task 8: Verify allowed actions and prompt schema snippets

**Files:**
- Modify: `backend/apps/agent/actions/matrix.py`
- Modify: `backend/apps/agent/llm/prompts.py`
- Modify: `backend/apps/agent/tests/test_prompts.py`

The `fill_form` and `submit_form` schema snippets already exist in `_ACTION_SCHEMA_SNIPPETS` (lines 84-93 of `prompts.py`). **The current `submit_form` snippet uses `"element_id": "form_1"` — this is wrong.** `SubmitFormAction` dispatches via `driver.click(element_id)`, which requires a **button** ID (e.g. `"btn_0"`) from the element registry. Form IDs (`form_0`, `form_1`) are not in the registry. Update the snippet example to `"btn_0"` to avoid `ValueError: Unknown element_id` at runtime.

- [ ] **Step 1: Write tests for allowed actions and prompt snippets**

Add to `test_prompts.py`:

```python
import pytest


@pytest.mark.parametrize("phase", ["probe", "verify"])
def test_probe_and_verify_prompts_include_fill_and_submit_schemas(phase):
    from apps.agent.llm.prompts import build_system_prompt
    from apps.agent.actions.matrix import allowed_actions_for_phase

    allowed_actions = allowed_actions_for_phase(phase)
    assert "fill_form" in allowed_actions
    assert "submit_form" in allowed_actions

    prompt = build_system_prompt(
        objective="test",
        phase=phase,
        allowed_actions=allowed_actions,
        budget_remaining=10,
    )
    assert "fill_form" in prompt
    assert "submit_form" in prompt
    assert '"element_id": "btn_0"' in prompt
    assert '"element_id": "form_1"' not in prompt


def test_enumerate_prompt_includes_fill_schema_only():
    from apps.agent.llm.prompts import build_system_prompt
    from apps.agent.actions.matrix import allowed_actions_for_phase

    allowed_actions = allowed_actions_for_phase("enumerate")
    assert "fill_form" in allowed_actions

    prompt = build_system_prompt(
        objective="test",
        phase="enumerate",
        allowed_actions=allowed_actions,
        budget_remaining=10,
    )
    assert "fill_form" in prompt
```

- [ ] **Step 2: Run tests to verify they fail for missing wiring**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_prompts.py -v`
Expected: FAIL if `fill_form`/`submit_form` are missing from the allowed-action matrix or if the submit snippet still uses `form_1`.

- [ ] **Step 3: Confirm allowed action matrix**

Task 1 should already have updated `actions/matrix.py`. If these entries are missing, add:

- `fill_form` to `enumerate`, `probe`, and `verify`
- `submit_form` to `probe` and `verify`

Do not add either form action to `recon` or `report`. Keep any existing phase order conventions intact so prompt output remains stable.

- [ ] **Step 4: Update submit_form prompt snippet**

In `prompts.py`, update only the `submit_form` example:

```python
{"action": "submit_form", "element_id": "btn_0", ...}
```

Do not use `form_0` or `form_1` in the submit example; `submit_form` clicks a submit button element.

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_prompts.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/agent/actions/matrix.py backend/apps/agent/llm/prompts.py backend/apps/agent/tests/test_prompts.py
git commit -m "fix(agent): expose form actions in prompts with button submit example"
```
