---
tier: FAST
depends_on: []
files:
  creates: []
  modifies:
    - backend/apps/agent/llm/prompts.py
    - backend/apps/agent/tests/test_prompts.py
  deletes: []
exports: []
imports: []
allow_extra_files: false
---

### Task 3: Extend build_system_prompt with prior intel section

**Files:**
- Modify: `backend/apps/agent/llm/prompts.py`
- Modify: `backend/apps/agent/tests/test_prompts.py`

- [ ] **Step 1: Write failing tests**

Add to `test_prompts.py`:

```python
class TestPriorIntelSection:
    def test_no_intel_means_no_section(self):
        prompt = build_system_prompt(
            objective="test", phase="recon",
            allowed_actions=["observe_page", "stop"],
            budget_remaining=10,
        )
        assert "Prior Target Intel" not in prompt

    def test_intel_section_injected(self):
        prompt = build_system_prompt(
            objective="test", phase="recon",
            allowed_actions=["observe_page", "stop"],
            budget_remaining=10,
            prior_intel_section="## Prior Target Intel\nKnown routes:\n  /login",
        )
        assert "Prior Target Intel" in prompt
        assert "/login" in prompt

    def test_intel_section_appears_after_budget(self):
        prompt = build_system_prompt(
            objective="test", phase="recon",
            allowed_actions=["observe_page", "stop"],
            budget_remaining=10,
            prior_intel_section="## Prior Target Intel\ntest",
        )
        budget_pos = prompt.index("Remaining turns")
        intel_pos = prompt.index("Prior Target Intel")
        safety_pos = prompt.index("Safety Rules")
        assert budget_pos < intel_pos < safety_pos
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_prompts.py::TestPriorIntelSection -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'prior_intel_section'`

- [ ] **Step 3: Implement prior_intel_section in build_system_prompt**

Modify `build_system_prompt` signature and `_SYSTEM_HEADER`:

Add `{prior_intel}` placeholder in `_SYSTEM_HEADER` between Budget and Safety Rules. The placeholder must include its own trailing blank line only when intel exists:

```python
## Budget
Remaining turns: {budget_remaining}

{prior_intel}## Safety Rules
```

Update `build_system_prompt`:

```python
def build_system_prompt(
    objective: str,
    phase: str,
    allowed_actions: list[str],
    budget_remaining: int,
    prior_intel_section: str = "",
) -> str:
    actions_str = "\n".join(f"  - {a}" for a in sorted(allowed_actions))
    action_schemas = _build_action_schemas(allowed_actions)
    prior_intel = prior_intel_section.strip()
    if prior_intel:
        prior_intel = f"{prior_intel}\n\n"
    return _SYSTEM_HEADER.format(
        objective=objective,
        phase=phase,
        allowed_actions=actions_str,
        budget_remaining=budget_remaining,
        prior_intel=prior_intel,
        action_schemas=action_schemas,
    )
```

The resulting rendered prompt should look like:

```text
## Budget
Remaining turns: 10

## Prior Target Intel
...

## Safety Rules
```

- [ ] **Step 4: Run ALL prompt tests**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_prompts.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/llm/prompts.py backend/apps/agent/tests/test_prompts.py
git commit -m "feat(agent): add optional prior_intel_section to system prompt"
```
