### Task 4: Action schemas with pydantic validation

**Files:**
- Create: `backend/apps/agent/actions/__init__.py`
- Create: `backend/apps/agent/actions/schemas.py`
- Create: `backend/apps/agent/tests/test_actions.py`

- [ ] **Step 1: Write tests for action schema validation**

```python
# backend/apps/agent/tests/test_actions.py
import pytest
from apps.agent.actions.schemas import (
    parse_action, ActionEnvelope, ObservePageAction,
    NavigateAction, InspectAssetAction, StoreNoteAction,
    SubmitCandidateAction, RequestPhaseTransitionAction, StopAction,
    InvalidActionError,
)


def test_parse_observe_page():
    raw = {
        "action": "observe_page",
        "goal": "See current state",
        "reason": "First turn",
        "args": {},
    }
    envelope = parse_action(raw)
    assert envelope.action == "observe_page"
    assert isinstance(envelope.parsed, ObservePageAction)


def test_parse_navigate_relative_path():
    raw = {
        "action": "navigate",
        "goal": "Check scoreboard",
        "args": {"path": "/score-board"},
    }
    envelope = parse_action(raw)
    assert envelope.parsed.path == "/score-board"


def test_parse_navigate_url_ref():
    raw = {
        "action": "navigate",
        "goal": "Follow discovered link",
        "args": {"url_ref": "url_5"},
    }
    envelope = parse_action(raw)
    assert envelope.parsed.url_ref == "url_5"


def test_navigate_rejects_absolute_url():
    raw = {
        "action": "navigate",
        "goal": "Go somewhere",
        "args": {"path": "https://evil.com/steal"},
    }
    with pytest.raises(InvalidActionError, match="absolute"):
        parse_action(raw)


def test_navigate_rejects_javascript_uri():
    raw = {
        "action": "navigate",
        "goal": "XSS",
        "args": {"path": "javascript:alert(1)"},
    }
    with pytest.raises(InvalidActionError, match="javascript"):
        parse_action(raw)


def test_navigate_rejects_protocol_relative():
    raw = {
        "action": "navigate",
        "goal": "Escape",
        "args": {"path": "//evil.com/path"},
    }
    with pytest.raises(InvalidActionError, match="protocol-relative"):
        parse_action(raw)


def test_parse_inspect_asset():
    raw = {
        "action": "inspect_asset",
        "goal": "Check JS bundle for routes",
        "args": {"asset_ref": "asset_2"},
    }
    envelope = parse_action(raw)
    assert envelope.parsed.asset_ref == "asset_2"


def test_parse_store_note():
    raw = {
        "action": "store_note",
        "goal": "Record finding",
        "args": {"note_type": "route", "content": {"path": "/admin"}},
    }
    envelope = parse_action(raw)
    assert envelope.parsed.note_type == "route"


def test_parse_submit_candidate():
    raw = {
        "action": "submit_candidate",
        "goal": "Found hidden page",
        "args": {
            "category": "hidden_route_discovered",
            "description": "Scoreboard at /score-board",
            "evidence_refs": ["obs_3", "act_5"],
        },
    }
    envelope = parse_action(raw)
    assert envelope.parsed.category == "hidden_route_discovered"


def test_parse_request_phase_transition():
    raw = {
        "action": "request_phase_transition",
        "goal": "Move to enumerate",
        "args": {
            "from_phase": "recon",
            "to_phase": "enumerate",
            "reason": "Baseline collected",
            "evidence_refs": ["obs_1"],
        },
    }
    envelope = parse_action(raw)
    assert envelope.parsed.to_phase == "enumerate"


def test_parse_stop():
    raw = {"action": "stop", "goal": "Done", "args": {"reason": "objective met"}}
    envelope = parse_action(raw)
    assert envelope.parsed.reason == "objective met"


def test_unknown_action_raises():
    raw = {"action": "hack_the_planet", "goal": "???", "args": {}}
    with pytest.raises(InvalidActionError, match="Unknown action"):
        parse_action(raw)


def test_missing_required_field_raises():
    raw = {"action": "navigate", "goal": "Go", "args": {}}
    with pytest.raises(InvalidActionError):
        parse_action(raw)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_actions.py -v`
Expected: FAIL — module not found


See [04-action-schemas-impl.md](04-action-schemas-impl.md) for Step 3 implementation code.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_actions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/actions/ backend/apps/agent/tests/test_actions.py
git commit -m "feat(agent): add typed action schemas with validation"
```
