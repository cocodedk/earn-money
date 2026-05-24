---
tier: FAST
depends_on: []
files:
  creates: []
  modifies:
    - backend/apps/agent/actions/schemas.py
    - backend/apps/agent/actions/matrix.py
    - backend/apps/agent/tests/test_actions.py
  deletes: []
exports:
  - FillFormAction
  - SubmitFormAction
imports: []
allow_extra_files: false
---

### Task 1: FillFormAction and SubmitFormAction dataclasses

**Files:**
- Modify: `backend/apps/agent/actions/schemas.py`
- Modify: `backend/apps/agent/actions/matrix.py`
- Modify: `backend/apps/agent/tests/test_actions.py`

- [ ] **Step 1: Write failing tests for FillFormAction**

Add to `test_actions.py`:

```python
class TestFillFormAction:
    def test_parse_valid_fill(self):
        raw = {
            "action": "fill_form", "goal": "g", "reason": "r",
            "hypothesis": "h", "element_id": "input_1", "value": "admin",
        }
        env = parse_action(raw)
        assert env.action == "fill_form"
        assert env.parsed.element_id == "input_1"
        assert env.parsed.value == "admin"

    def test_reject_missing_element_id(self):
        raw = {
            "action": "fill_form", "goal": "g", "reason": "r",
            "hypothesis": "h", "value": "test",
        }
        with pytest.raises(InvalidActionError, match="element_id"):
            parse_action(raw)

    def test_reject_empty_element_id(self):
        raw = {
            "action": "fill_form", "goal": "g", "reason": "r",
            "hypothesis": "h", "element_id": "", "value": "test",
        }
        with pytest.raises(InvalidActionError, match="element_id"):
            parse_action(raw)

    def test_empty_value_clears_field(self):
        raw = {
            "action": "fill_form", "goal": "g", "reason": "r",
            "hypothesis": "h", "element_id": "input_0", "value": "",
        }
        env = parse_action(raw)
        assert env.parsed.value == ""

    def test_reject_missing_value(self):
        raw = {
            "action": "fill_form", "goal": "g", "reason": "r",
            "hypothesis": "h", "element_id": "input_0",
        }
        with pytest.raises(InvalidActionError, match="value"):
            parse_action(raw)

    def test_reject_null_value(self):
        raw = {
            "action": "fill_form", "goal": "g", "reason": "r",
            "hypothesis": "h", "element_id": "input_0", "value": None,
        }
        with pytest.raises(InvalidActionError, match="value"):
            parse_action(raw)


class TestSubmitFormAction:
    def test_parse_valid_submit(self):
        raw = {
            "action": "submit_form", "goal": "g", "reason": "r",
            "hypothesis": "h", "element_id": "btn_0",
        }
        env = parse_action(raw)
        assert env.action == "submit_form"
        assert env.parsed.element_id == "btn_0"

    def test_reject_missing_element_id(self):
        raw = {
            "action": "submit_form", "goal": "g", "reason": "r",
            "hypothesis": "h",
        }
        with pytest.raises(InvalidActionError, match="element_id"):
            parse_action(raw)

    def test_reject_empty_element_id(self):
        raw = {
            "action": "submit_form", "goal": "g", "reason": "r",
            "hypothesis": "h", "element_id": "",
        }
        with pytest.raises(InvalidActionError, match="element_id"):
            parse_action(raw)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_actions.py::TestFillFormAction apps/agent/tests/test_actions.py::TestSubmitFormAction -v`
Expected: FAIL — `Unknown action 'fill_form'`

- [ ] **Step 3: Implement FillFormAction and SubmitFormAction**

Add to `schemas.py` after `HttpRequestAction`:

```python
@dataclass
class FillFormAction:
    element_id: str
    value: str

    def __post_init__(self) -> None:
        if not self.element_id:
            raise InvalidActionError("fill_form requires a non-empty element_id")
        if self.value is None:
            raise InvalidActionError("fill_form requires value")
        if not isinstance(self.value, str):
            raise InvalidActionError("fill_form value must be a string")


@dataclass
class SubmitFormAction:
    element_id: str

    def __post_init__(self) -> None:
        if not self.element_id:
            raise InvalidActionError("submit_form requires a non-empty element_id")
```

Add to `_ACTION_MAP`:

```python
"fill_form": FillFormAction,
"submit_form": SubmitFormAction,
```

Register the new actions in `actions/matrix.py` at the same time:

- `fill_form` in `enumerate`, `probe`, and `verify`
- `submit_form` in `probe` and `verify`

Do not add either form action to `recon` or `report`.

If missing dataclass fields currently surface as `TypeError`, keep the existing parser behavior consistent by wrapping that error in `InvalidActionError` with the missing field name. The `test_reject_missing_value` assertion must fail cleanly with `InvalidActionError`, not an uncaught constructor exception.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_actions.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/actions/schemas.py backend/apps/agent/actions/matrix.py backend/apps/agent/tests/test_actions.py
git commit -m "feat(agent): add FillFormAction and SubmitFormAction dataclasses"
```
