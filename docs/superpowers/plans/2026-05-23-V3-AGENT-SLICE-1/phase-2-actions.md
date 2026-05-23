# Phase 2 — Action Schemas & Phase Matrix

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

- [ ] **Step 3: Implement action schemas**

```python
# backend/apps/agent/actions/__init__.py
from .schemas import parse_action, ActionEnvelope, InvalidActionError

__all__ = ["parse_action", "ActionEnvelope", "InvalidActionError"]
```

```python
# backend/apps/agent/actions/schemas.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class InvalidActionError(ValueError):
    pass


@dataclass(frozen=True)
class ObservePageAction:
    include_screenshot: bool = False
    element_ids: list[str] | None = None


@dataclass(frozen=True)
class NavigateAction:
    path: str | None = None
    url_ref: str | None = None


@dataclass(frozen=True)
class InspectAssetAction:
    asset_ref: str


@dataclass(frozen=True)
class StoreNoteAction:
    note_type: str
    content: dict[str, Any]


@dataclass(frozen=True)
class SubmitCandidateAction:
    category: str
    description: str
    evidence_refs: list[str]


@dataclass(frozen=True)
class RequestPhaseTransitionAction:
    from_phase: str
    to_phase: str
    reason: str
    evidence_refs: list[str]
    remaining_questions: list[str] | None = None


@dataclass(frozen=True)
class StopAction:
    reason: str


VALID_NOTE_TYPES = {"hypothesis", "gap", "credential_label", "route", "parameter", "candidate"}

_SCHEMA_MAP: dict[str, type] = {
    "observe_page": ObservePageAction,
    "navigate": NavigateAction,
    "inspect_asset": InspectAssetAction,
    "store_note": StoreNoteAction,
    "submit_candidate": SubmitCandidateAction,
    "request_phase_transition": RequestPhaseTransitionAction,
    "stop": StopAction,
}


@dataclass(frozen=True)
class ActionEnvelope:
    action: str
    goal: str
    reason: str
    hypothesis: str
    parsed: Any


def _validate_navigate(args: dict[str, Any]) -> NavigateAction:
    path = args.get("path")
    url_ref = args.get("url_ref")
    if not path and not url_ref:
        raise InvalidActionError("navigate requires 'path' or 'url_ref'")
    if path:
        if path.startswith("javascript:"):
            raise InvalidActionError("javascript: URIs are forbidden")
        if path.startswith("data:"):
            raise InvalidActionError("data: URIs are forbidden")
        if path.startswith("//"):
            raise InvalidActionError("protocol-relative URLs are forbidden")
        if "://" in path:
            raise InvalidActionError("absolute URLs are forbidden — use relative paths")
    return NavigateAction(path=path, url_ref=url_ref)


def parse_action(raw: dict[str, Any]) -> ActionEnvelope:
    action_name = raw.get("action")
    if not action_name or action_name not in _SCHEMA_MAP:
        raise InvalidActionError(f"Unknown action: {action_name!r}")

    goal = raw.get("goal", "")
    reason = raw.get("reason", "")
    hypothesis = raw.get("hypothesis", "")
    args = raw.get("args", {})

    if action_name == "navigate":
        parsed = _validate_navigate(args)
    elif action_name == "observe_page":
        parsed = ObservePageAction(
            include_screenshot=args.get("include_screenshot", False),
            element_ids=args.get("element_ids"),
        )
    elif action_name == "inspect_asset":
        ref = args.get("asset_ref")
        if not ref:
            raise InvalidActionError("inspect_asset requires 'asset_ref'")
        parsed = InspectAssetAction(asset_ref=ref)
    elif action_name == "store_note":
        nt = args.get("note_type")
        if nt not in VALID_NOTE_TYPES:
            raise InvalidActionError(f"Invalid note_type: {nt!r}")
        parsed = StoreNoteAction(note_type=nt, content=args.get("content", {}))
    elif action_name == "submit_candidate":
        parsed = SubmitCandidateAction(
            category=args.get("category", ""),
            description=args.get("description", ""),
            evidence_refs=args.get("evidence_refs", []),
        )
    elif action_name == "request_phase_transition":
        for field in ("from_phase", "to_phase", "reason"):
            if field not in args:
                raise InvalidActionError(f"request_phase_transition requires '{field}'")
        parsed = RequestPhaseTransitionAction(
            from_phase=args["from_phase"], to_phase=args["to_phase"],
            reason=args["reason"], evidence_refs=args.get("evidence_refs", []),
            remaining_questions=args.get("remaining_questions"),
        )
    elif action_name == "stop":
        parsed = StopAction(reason=args.get("reason", ""))
    else:
        raise InvalidActionError(f"Unknown action: {action_name!r}")

    return ActionEnvelope(
        action=action_name, goal=goal, reason=reason,
        hypothesis=hypothesis, parsed=parsed,
    )
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_actions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/actions/ backend/apps/agent/tests/test_actions.py
git commit -m "feat(agent): add typed action schemas with validation"
```

### Task 5: Phase-action matrix enforcement

**Files:**
- Create: `backend/apps/agent/actions/matrix.py`
- Modify: `backend/apps/agent/tests/test_actions.py`

- [ ] **Step 1: Write tests for matrix enforcement**

```python
# append to backend/apps/agent/tests/test_actions.py
from apps.agent.actions.matrix import check_phase_action, PhaseViolationError


def test_observe_page_allowed_in_recon():
    check_phase_action("recon", "observe_page")


def test_observe_page_denied_in_report():
    with pytest.raises(PhaseViolationError):
        check_phase_action("report", "observe_page")


def test_navigate_allowed_in_enumerate():
    check_phase_action("enumerate", "navigate")


def test_submit_candidate_denied_in_recon():
    with pytest.raises(PhaseViolationError):
        check_phase_action("recon", "submit_candidate")


def test_submit_candidate_allowed_in_enumerate():
    check_phase_action("enumerate", "submit_candidate")


def test_store_note_allowed_everywhere():
    for phase in ("recon", "enumerate", "probe", "verify", "report"):
        check_phase_action(phase, "store_note")


def test_stop_allowed_everywhere():
    for phase in ("recon", "enumerate", "probe", "verify", "report"):
        check_phase_action(phase, "stop")


def test_inspect_asset_denied_in_report():
    with pytest.raises(PhaseViolationError):
        check_phase_action("report", "inspect_asset")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_actions.py -v -k "phase"` 
Expected: FAIL

- [ ] **Step 3: Implement matrix**

```python
# backend/apps/agent/actions/matrix.py
from __future__ import annotations


class PhaseViolationError(ValueError):
    pass


_PHASE_ACTION_MATRIX: dict[str, set[str]] = {
    "recon": {
        "observe_page", "navigate", "inspect_asset",
        "store_note", "request_phase_transition", "stop",
    },
    "enumerate": {
        "observe_page", "navigate", "click", "fill_form",
        "inspect_asset", "store_note", "submit_candidate",
        "request_phase_transition", "stop",
    },
    "probe": {
        "observe_page", "navigate", "click", "fill_form", "submit_form",
        "http_request", "run_stub", "run_tool", "inspect_asset",
        "store_note", "submit_candidate", "request_verify",
        "request_phase_transition", "stop",
    },
    "verify": {
        "observe_page", "navigate", "click", "fill_form", "submit_form",
        "http_request", "store_note", "submit_candidate",
        "request_verify", "request_phase_transition", "stop",
    },
    "report": {
        "store_note", "submit_candidate", "stop",
    },
}


def check_phase_action(phase: str, action: str) -> None:
    allowed = _PHASE_ACTION_MATRIX.get(phase)
    if allowed is None:
        raise PhaseViolationError(f"Unknown phase: {phase!r}")
    if action not in allowed:
        raise PhaseViolationError(
            f"Action {action!r} is not allowed in phase {phase!r}"
        )
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_actions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/actions/matrix.py backend/apps/agent/tests/test_actions.py
git commit -m "feat(agent): add phase-action matrix enforcement"
```
