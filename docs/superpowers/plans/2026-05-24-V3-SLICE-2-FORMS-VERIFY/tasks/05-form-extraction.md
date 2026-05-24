---
tier: CAPABLE
depends_on: []
files:
  creates: []
  modifies:
    - backend/apps/agent/observations/builder.py
    - backend/apps/agent/tests/test_builder.py
  deletes: []
exports:
  - ObservationBuilder._parse_form_node
imports: []
allow_extra_files: false
---

### Task 5: Form grouping in observation builder

**Files:**
- Modify: `backend/apps/agent/observations/builder.py`
- Modify: `backend/apps/agent/tests/test_builder.py`

- [ ] **Step 1: Write failing tests for form extraction**

Add to `test_builder.py`:

```python
class TestFormExtraction:
    def test_form_node_creates_form_element(self):
        builder = ObservationBuilder("https://example.com")
        children = [
            {
                "role": "form",
                "name": "Login",
                "children": [
                    {"role": "textbox", "name": "Email"},
                    {"role": "textbox", "name": "Password"},
                    {"role": "button", "name": "Sign In", "type": "submit"},
                ],
            },
        ]
        elements, visible = builder._parse_a11y(children)
        assert len(elements.forms) == 1
        assert elements.forms[0].element_id.startswith("form_")
        assert len(elements.forms[0].fields) == 2
        assert len(elements.inputs) == 2
        assert len(elements.buttons) == 1

    def test_orphan_inputs_remain_standalone(self):
        builder = ObservationBuilder("https://example.com")
        children = [
            {"role": "textbox", "name": "Search"},
            {"role": "button", "name": "Go"},
        ]
        elements, visible = builder._parse_a11y(children)
        assert len(elements.forms) == 0
        assert len(elements.inputs) == 1
        assert len(elements.buttons) == 1

    def test_form_fields_have_correct_types(self):
        builder = ObservationBuilder("https://example.com")
        children = [
            {
                "role": "form",
                "name": "Register",
                "children": [
                    {"role": "textbox", "name": "Username"},
                    {"role": "combobox", "name": "Country"},
                    {"role": "searchbox", "name": "Filter"},
                ],
            },
        ]
        elements, visible = builder._parse_a11y(children)
        form = elements.forms[0]
        assert form.fields[0].type == "textbox"
        assert form.fields[1].type == "combobox"
        assert form.fields[2].type == "searchbox"

    def test_nested_form_controls_are_grouped(self):
        builder = ObservationBuilder("https://example.com")
        children = [
            {
                "role": "form",
                "name": "Login",
                "children": [
                    {
                        "role": "group",
                        "name": "Credentials",
                        "children": [
                            {"role": "textbox", "name": "Email"},
                            {"role": "textbox", "name": "Password"},
                            {"role": "button", "name": "Sign In", "type": "submit"},
                        ],
                    },
                ],
            },
        ]
        elements, visible = builder._parse_a11y(children)
        assert len(elements.forms) == 1
        assert [field.name for field in elements.forms[0].fields] == [
            "Email", "Password",
        ]
        assert len(elements.inputs) == 2
        assert len(elements.buttons) == 1
```

Import `ObservationBuilder` at the top of the test file if not already imported.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_builder.py::TestFormExtraction -v`
Expected: FAIL — forms list is empty, form grouping not implemented

- [ ] **Step 3: Implement form grouping in _parse_a11y**

Follow the detailed implementation patch in [05-form-extraction-implementation.md](05-form-extraction-implementation.md). It keeps the original link/button/input parsing behavior, adds recursive descendant handling for controls nested inside form containers, and adds the required `FormElement`/`FormField` imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_builder.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/observations/builder.py backend/apps/agent/tests/test_builder.py
git commit -m "feat(agent): extract form elements from a11y snapshot"
```
