# V3 Slice 2 — Forms + Verify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Playwright-based form interaction (fill_form, submit_form) and the verify phase so the agent can fill forms, submit them, and replay findings for confirmation.

**Architecture:** Two new action dataclasses + driver methods feed through the existing dispatch/observe/emit pipeline. The verify phase reuses probe actions with a tighter budget and a candidate-existence gate. Form elements are extracted from the accessibility snapshot and grouped by parent form node.

**Tech Stack:** Django, Playwright (async), pytest, asyncio

---

## File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/apps/agent/actions/schemas.py` | Modify | Add `FillFormAction`, `SubmitFormAction` dataclasses + register in `_ACTION_MAP` |
| `backend/apps/agent/browser/driver.py` | Modify | Add `fill(element_id, value)` method |
| `backend/apps/agent/controller_dispatch.py` | Modify | Add dispatch branches for `fill_form` and `submit_form` |
| `backend/apps/agent/controller.py` | Modify | Add verify-phase entry gate (candidate exists) |
| `backend/apps/agent/mission_profiles.py` | Modify | Add `form_fills`, `form_submits`, `verify_turns` budget keys; add `juice_shop_login` profile |
| `backend/apps/agent/observations/builder.py` | Modify | Add form grouping from a11y snapshot |
| `backend/apps/agent/observations/page.py` | No change | `FormElement`, `FormField`, `InputElement` already exist |
| `backend/apps/agent/tests/test_actions.py` | Modify | Add tests for FillFormAction, SubmitFormAction |
| `backend/apps/agent/tests/test_driver.py` | Modify | Add tests for driver.fill() |
| `backend/apps/agent/tests/test_controller.py` | Modify | Add tests for fill_form/submit_form dispatch + verify phase |
| `backend/apps/agent/tests/test_builder.py` | Modify | Add tests for form grouping |
| `backend/apps/agent/tests/test_mission_profiles.py` | Modify | Add tests for new profile + budget keys |

---

### Task 1: FillFormAction and SubmitFormAction dataclasses

**Files:**
- Modify: `backend/apps/agent/actions/schemas.py`
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_actions.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/actions/schemas.py backend/apps/agent/tests/test_actions.py
git commit -m "feat(agent): add FillFormAction and SubmitFormAction dataclasses"
```

---

### Task 2: Driver fill() method

**Files:**
- Modify: `backend/apps/agent/browser/driver.py`
- Modify: `backend/apps/agent/tests/test_driver.py`

- [ ] **Step 1: Write failing tests for driver.fill()**

Add to `test_driver.py`:

```python
class TestDriverFill:
    def test_fill_known_element(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"input_1": "input[name='email']"}
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator
        locator.fill = AsyncMock()
        driver._page = page

        run(driver.fill("input_1", "admin@example.com"))
        page.locator.assert_called_once_with("input[name='email']")
        locator.fill.assert_awaited_once_with("admin@example.com")

    def test_fill_unknown_element_raises(self):
        driver = PlaywrightDriver()
        driver._element_registry = {}
        with pytest.raises(ValueError, match="Unknown element_id"):
            run(driver.fill("input_999", "test"))

    def test_fill_empty_value_clears(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"input_0": "input[name='q']"}
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator
        locator.fill = AsyncMock()
        driver._page = page

        run(driver.fill("input_0", ""))
        locator.fill.assert_awaited_once_with("")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_driver.py::TestDriverFill -v`
Expected: FAIL — `PlaywrightDriver has no attribute 'fill'`

- [ ] **Step 3: Implement fill() method**

Add to `driver.py` after the `click` method:

```python
async def fill(self, element_id: str, value: str) -> None:
    """Fill the input identified by element_id with value."""
    if element_id not in self._element_registry:
        raise ValueError(f"Unknown element_id: {element_id!r}")
    selector = self._element_registry[element_id]
    locator = self._page.locator(selector)
    await locator.fill(value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_driver.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/browser/driver.py backend/apps/agent/tests/test_driver.py
git commit -m "feat(agent): add fill() method to PlaywrightDriver"
```

---

### Task 3: Dispatch fill_form and submit_form actions

**Files:**
- Modify: `backend/apps/agent/controller_dispatch.py`
- Modify: `backend/apps/agent/tests/test_controller.py`

- [ ] **Step 1: Write failing tests for fill_form dispatch**

Add to `test_controller.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestFillFormExecution:
    @pytest.mark.asyncio
    async def test_fill_form_calls_driver_fill(self, db_objects):
        fill_json = _action_json(
            action="fill_form", element_id="input_0", value="admin",
        )
        ctrl = _ctrl(db_objects, responses=[fill_json], budget={"max_turns": 5})
        ctrl.session.current_phase = "enumerate"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.fill = AsyncMock()

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.fill.assert_awaited_once_with("input_0", "admin")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="page",
        ).exists()


@pytest.mark.django_db(transaction=True)
class TestSubmitFormExecution:
    @pytest.mark.asyncio
    async def test_submit_form_calls_driver_click(self, db_objects):
        submit_json = _action_json(
            action="submit_form", element_id="btn_0",
        )
        ctrl = _ctrl(db_objects, responses=[submit_json], budget={"max_turns": 5})
        ctrl.session.current_phase = "probe"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.click = AsyncMock()

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.click.assert_awaited_once_with("btn_0")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="page",
        ).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py::TestFillFormExecution apps/agent/tests/test_controller.py::TestSubmitFormExecution -v`
Expected: FAIL — `Unknown action 'fill_form'` or no dispatch branch

- [ ] **Step 3: Implement dispatch branches**

In `controller_dispatch.py`, add imports at the top:

```python
from .actions.schemas import (
    ClickAction, FillFormAction, HttpRequestAction, NavigateAction,
    RequestPhaseTransitionAction, StopAction, StoreNoteAction, SubmitFormAction,
)
```

Add dispatch branches in `dispatch()` after the `ClickAction` branch:

```python
if isinstance(parsed, FillFormAction):
    await ctrl.driver.fill(parsed.element_id, parsed.value)
    obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
    ctrl.budget.consume("form_fills")
    _emit_and_finish_browser(ctrl, turn, envelope, obs_dict)
    return False

if isinstance(parsed, SubmitFormAction):
    await ctrl.driver.click(parsed.element_id)
    obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
    ctrl.budget.consume("form_submits")
    _emit_and_finish_browser(ctrl, turn, envelope, obs_dict)
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/controller_dispatch.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): dispatch fill_form and submit_form actions"
```

---

### Task 4: Verify phase entry gate

**Files:**
- Modify: `backend/apps/agent/controller.py`
- Modify: `backend/apps/agent/controller_dispatch.py`
- Modify: `backend/apps/agent/tests/test_controller.py`

- [ ] **Step 1: Write failing tests for verify phase gate**

Add to `test_controller.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestVerifyPhaseGate:
    @pytest.mark.asyncio
    async def test_verify_transition_denied_without_candidate(self, db_objects):
        """Transition to verify is denied if no submit_candidate exists."""
        c = _ctrl(db_objects, [
            _action_json(
                "request_phase_transition", from_phase="probe",
                to_phase="verify", evidence_refs=[],
            ),
            _action_json("stop"),
        ])
        c.session.current_phase = "probe"
        c.session.save(update_fields=["current_phase"])
        c._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]
        await c.run()
        c.session.refresh_from_db()
        assert c.session.current_phase != "verify"

    @pytest.mark.asyncio
    async def test_verify_transition_allowed_with_candidate(self, db_objects):
        """Transition to verify is allowed when a submit_candidate action exists."""
        c = _ctrl(db_objects, [
            _action_json(
                "submit_candidate", category="xss",
                description="test", evidence_refs=[],
            ),
            _action_json(
                "request_phase_transition", from_phase="probe",
                to_phase="verify", evidence_refs=[],
            ),
            _action_json("stop"),
        ])
        c.session.current_phase = "probe"
        c.session.save(update_fields=["current_phase"])
        c._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]
        await c.run()
        c.session.refresh_from_db()
        assert c.session.current_phase == "report"
        assert c.session.status == "completed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py::TestVerifyPhaseGate -v`
Expected: FAIL — verify transition proceeds without candidate check

- [ ] **Step 3: Implement verify gate in phase transition handler**

In `controller_dispatch.py`, modify `_handle_phase_transition`:

```python
def _handle_phase_transition(ctrl, parsed) -> None:
    from .phases import is_valid_transition

    if not is_valid_transition(parsed.from_phase, parsed.to_phase):
        return

    if parsed.to_phase == "verify" and not _has_candidate(ctrl.session):
        return

    from .event_log import build_budget_snapshot, emit_phase_changed
    snapshot = build_budget_snapshot(
        ctrl.session, ctrl.budget.consumed_snapshot(),
    )
    emit_phase_changed(
        ctrl.session, parsed.from_phase, parsed.to_phase, parsed.reason,
        budget_snapshot=snapshot,
    )
    ctrl.advance_phase(parsed.to_phase, parsed.reason)


def _has_candidate(session) -> bool:
    """Return True if the session has at least one submit_candidate action."""
    from .models import AgentAction
    return AgentAction.objects.filter(
        turn__session=session,
        action_type="submit_candidate",
    ).exists()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/controller_dispatch.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): add verify phase entry gate — requires candidate"
```

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
```

Import `ObservationBuilder` at the top of the test file if not already imported.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_builder.py::TestFormExtraction -v`
Expected: FAIL — forms list is empty, form grouping not implemented

- [ ] **Step 3: Implement form grouping in _parse_a11y**

Modify `_parse_a11y` in `builder.py` to handle `role=form` nodes:

```python
def _parse_a11y(
    self, children: list[dict]
) -> tuple[Elements, list[VisibleTextBlock]]:
    links: list[LinkElement] = []
    buttons: list[ButtonElement] = []
    inputs: list[InputElement] = []
    forms: list[FormElement] = []
    visible: list[VisibleTextBlock] = []

    for node in children:
        role = node.get("role", "")
        name = node.get("name", "")

        if role == "form":
            form_elem, form_inputs, form_buttons, form_visible = (
                self._parse_form_node(node)
            )
            forms.append(form_elem)
            inputs.extend(form_inputs)
            buttons.extend(form_buttons)
            visible.extend(form_visible)
            continue

        if role == "link":
            href = node.get("url", "") or node.get("value", "")
            links.append(LinkElement(
                element_id=self._next_id("link"),
                href=href,
                text=name,
            ))
        elif role == "button":
            buttons.append(ButtonElement(
                element_id=self._next_id("btn"),
                text=name,
                type=node.get("type", "button"),
            ))
        elif role in ("textbox", "searchbox", "combobox"):
            inputs.append(InputElement(
                element_id=self._next_id("input"),
                name=name,
                type=role,
                placeholder=node.get("placeholder", ""),
            ))
        if name:
            visible.append(VisibleTextBlock(text=name))

    return Elements(links=links, buttons=buttons, forms=forms, inputs=inputs), visible
```

Add the `_parse_form_node` helper:

```python
def _parse_form_node(self, node: dict) -> tuple:
    """Parse a role=form a11y node into form element + children."""
    from .page import FormField

    form_id = self._next_id("form")
    name = node.get("name", "")
    form_children = node.get("children", [])
    fields: list[FormField] = []
    inputs: list[InputElement] = []
    buttons: list[ButtonElement] = []
    visible: list[VisibleTextBlock] = []

    for child in form_children:
        child_role = child.get("role", "")
        child_name = child.get("name", "")
        if child_role in ("textbox", "searchbox", "combobox"):
            input_id = self._next_id("input")
            fields.append(FormField(
                name=child_name,
                type=child_role,
            ))
            inputs.append(InputElement(
                element_id=input_id,
                name=child_name,
                type=child_role,
                placeholder=child.get("placeholder", ""),
            ))
        elif child_role == "button":
            buttons.append(ButtonElement(
                element_id=self._next_id("btn"),
                text=child_name,
                type=child.get("type", "button"),
            ))
        if child_name:
            visible.append(VisibleTextBlock(text=child_name))

    form_elem = FormElement(
        element_id=form_id,
        action="",
        method="POST",
        fields=fields,
    )
    if name:
        visible.insert(0, VisibleTextBlock(text=name))
    return form_elem, inputs, buttons, visible
```

Add the `FormElement` and `FormField` imports at the top of `builder.py`:

```python
from .page import (
    ButtonElement,
    CookieInfo,
    DiscoveredAsset,
    DiscoveredItems,
    DiscoveredRoute,
    Elements,
    FormElement,
    FormField,
    InputElement,
    LinkElement,
    NetworkEntry,
    ObservationMeta,
    PageIdentity,
    PageObservation,
    VisibleTextBlock,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_builder.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/observations/builder.py backend/apps/agent/tests/test_builder.py
git commit -m "feat(agent): extract form elements from a11y snapshot"
```

---

### Task 6: Budget keys and mission profile update

**Files:**
- Modify: `backend/apps/agent/mission_profiles.py`
- Modify: `backend/apps/agent/tests/test_mission_profiles.py`

- [ ] **Step 1: Write failing tests for new budget keys**

Add to `test_mission_profiles.py`:

```python
class TestJuiceShopLoginProfile:
    def setup_method(self):
        self.profile = get_profile("juice_shop_login")

    def test_name(self):
        assert self.profile.name == "juice_shop_login"

    def test_phases_include_verify(self):
        assert "verify" in self.profile.phases

    def test_mission_budget_has_form_keys(self):
        budget = self.profile.mission_budget
        assert "max_form_fills" in budget
        assert "max_form_submits" in budget

    def test_verify_phase_budget_exists(self):
        assert "verify" in self.profile.phase_budgets
        assert "max_turns" in self.profile.phase_budgets["verify"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_mission_profiles.py::TestJuiceShopLoginProfile -v`
Expected: FAIL — `KeyError: 'juice_shop_login'`

- [ ] **Step 3: Add juice_shop_login profile**

Add to `_PROFILES` in `mission_profiles.py`:

```python
"juice_shop_login": MissionProfile(
    name="juice_shop_login",
    target="juiceshop.cocode.dk",
    objective=(
        "Discover login/registration forms on OWASP Juice Shop, "
        "attempt common credential combinations, and verify "
        "any authentication bypass or weak credential findings."
    ),
    success_category="broken_authentication",
    phases=["recon", "enumerate", "probe", "verify", "report"],
    mission_budget={
        "max_turns": 40,
        "max_runtime_seconds": 300,
        "max_llm_calls": 35,
        "max_http_requests": 60,
        "max_browser_actions": 50,
        "max_asset_inspections": 10,
        "max_form_fills": 50,
        "max_form_submits": 20,
    },
    phase_budgets={
        "recon": {
            "max_turns": 6,
            "max_browser_actions": 10,
        },
        "enumerate": {
            "max_turns": 10,
            "max_browser_actions": 20,
            "max_form_fills": 15,
        },
        "probe": {
            "max_turns": 12,
            "max_browser_actions": 20,
            "max_form_fills": 25,
            "max_form_submits": 15,
        },
        "verify": {
            "max_turns": 8,
            "max_browser_actions": 10,
            "max_form_fills": 10,
            "max_form_submits": 5,
        },
        "report": {
            "max_turns": 4,
        },
    },
    model_policy={},
),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_mission_profiles.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/mission_profiles.py backend/apps/agent/tests/test_mission_profiles.py
git commit -m "feat(agent): add juice_shop_login profile with form budgets and verify phase"
```

---

### Task 7: End-to-end controller test — fill → submit → verify → stop

**Files:**
- Modify: `backend/apps/agent/tests/test_controller.py`

- [ ] **Step 1: Write end-to-end test**

Add to `test_controller.py`:

```python
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_full_form_flow_with_verify(db_objects):
    """Agent fills a form, submits, transitions to verify, replays, stops."""
    c = _ctrl(db_objects, [
        _action_json("navigate", path="/login"),
        _action_json("fill_form", element_id="input_0", value="admin"),
        _action_json("fill_form", element_id="input_1", value="password"),
        _action_json("submit_form", element_id="btn_0"),
        _action_json(
            "submit_candidate", category="weak_creds",
            description="default login", evidence_refs=[],
        ),
        _action_json(
            "request_phase_transition", from_phase="probe",
            to_phase="verify", evidence_refs=[],
        ),
        _action_json("navigate", path="/login"),
        _action_json("fill_form", element_id="input_0", value="admin"),
        _action_json("submit_form", element_id="btn_0"),
        _action_json("stop"),
    ], budget={"max_turns": 20})
    c.session.current_phase = "probe"
    c.session.save(update_fields=["current_phase"])
    c._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]
    c.driver.fill = AsyncMock()
    c.driver.click = AsyncMock()

    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == "completed"
    from apps.agent.models import AgentAction
    fills = AgentAction.objects.filter(
        turn__session=c.session, action_type="fill_form",
    )
    assert fills.count() == 3
    submits = AgentAction.objects.filter(
        turn__session=c.session, action_type="submit_form",
    )
    assert submits.count() == 2
```

- [ ] **Step 2: Run test to verify it passes**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py::test_full_form_flow_with_verify -v`
Expected: PASS (all pieces wired up from previous tasks)

- [ ] **Step 3: Run full test suite**

Run: `docker compose exec backend python -m pytest apps/agent/tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/apps/agent/tests/test_controller.py
git commit -m "test(agent): add end-to-end form flow with verify phase"
```

---

### Task 8: Update prompts schema snippets

**Files:**
- Modify: `backend/apps/agent/llm/prompts.py`

The `fill_form` and `submit_form` schema snippets already exist in `_ACTION_SCHEMA_SNIPPETS` (lines 84-93). The current `fill_form` snippet says `"element_id": "form_1"` for submit_form. Verify this matches the new `SubmitFormAction` which uses `element_id` for the submit button, not a form element. The existing snippet already matches (`"element_id": "form_1"` is the button/form submit target) — no code change needed, but verify in the test.

- [ ] **Step 1: Write test confirming prompts include fill_form and submit_form**

Add to an existing prompts test file or `test_controller.py`:

```python
def test_probe_prompt_includes_fill_and_submit_schemas():
    from apps.agent.llm.prompts import build_system_prompt
    from apps.agent.actions.matrix import allowed_actions_for_phase

    prompt = build_system_prompt(
        objective="test",
        phase="probe",
        allowed_actions=allowed_actions_for_phase("probe"),
        budget_remaining=10,
    )
    assert "fill_form" in prompt
    assert "submit_form" in prompt
    assert "element_id" in prompt
```

- [ ] **Step 2: Run test**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_prompts.py -v`
Expected: PASS

- [ ] **Step 3: Commit if any changes were needed**

Only commit if prompt snippets needed updating. Otherwise skip.
