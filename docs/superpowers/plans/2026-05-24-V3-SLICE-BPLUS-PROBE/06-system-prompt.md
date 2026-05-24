# Task 6: System Prompt — Add click + http_request Schemas

**Files:**
- Modify: `backend/apps/agent/llm/prompts.py`
- Modify: `backend/apps/agent/tests/test_prompts.py`

---

- [ ] **Step 1: Write test for click schema in probe prompt**

Add to `backend/apps/agent/tests/test_prompts.py`:

```python
class TestProbePromptSchemas:
    def test_probe_prompt_includes_click(self):
        prompt = build_system_prompt(
            objective="test",
            phase="probe",
            allowed_actions=allowed_actions_for_phase("probe"),
            budget_remaining=10,
        )
        assert "click" in prompt
        assert "element_id" in prompt

    def test_probe_prompt_includes_http_request(self):
        prompt = build_system_prompt(
            objective="test",
            phase="probe",
            allowed_actions=allowed_actions_for_phase("probe"),
            budget_remaining=10,
        )
        assert "http_request" in prompt
        assert '"method"' in prompt
        assert '"path"' in prompt

    def test_report_prompt_excludes_click(self):
        prompt = build_system_prompt(
            objective="test",
            phase="report",
            allowed_actions=allowed_actions_for_phase("report"),
            budget_remaining=5,
        )
        assert "click" not in prompt
        assert "http_request" not in prompt
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_prompts.py::TestProbePromptSchemas -v`

- [ ] **Step 3: Add click + http_request schemas to SYSTEM_TEMPLATE**

In `backend/apps/agent/llm/prompts.py`, add to the Action Schemas section
after `### inspect_asset`:

```python
### click
{{ "action": "click", "goal": "...", "reason": "...", "hypothesis": "...",
   "element_id": "link_3" }}

### http_request
{{ "action": "http_request", "goal": "...", "reason": "...", "hypothesis": "...",
   "method": "GET", "path": "/api/endpoint" }}
   method must be GET or HEAD. Same-origin only. No request body.
```

The prompt already uses `{allowed_actions}` to list permitted actions per
phase, so click/http_request schemas are visible only when the phase matrix
includes them.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Run all prompt tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_prompts.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/apps/agent/llm/prompts.py backend/apps/agent/tests/test_prompts.py
git commit -m "feat(agent): add click + http_request schemas to system prompt"
```
