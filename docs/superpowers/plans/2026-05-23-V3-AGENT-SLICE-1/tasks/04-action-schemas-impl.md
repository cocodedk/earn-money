# 04-action-schemas — Implementation Code

Part of [Task 04](04-action-schemas.md). This file contains Step 3.

- [ ] **Step 3: Implement action schemas**

```python
# backend/apps/agent/actions/__init__.py
from .schemas import parse_action, ActionEnvelope, InvalidActionError

__all__ = ["parse_action", "ActionEnvelope", "InvalidActionError"]
```

```python
# backend/apps/agent/actions/schemas.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


class InvalidActionError(ValueError):
    pass


class _ActionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObservePageAction(_ActionModel):
    include_screenshot: bool = False
    element_ids: list[str] | None = None


class NavigateAction(_ActionModel):
    path: str | None = None
    url_ref: str | None = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        lowered = value.lower()
        if lowered.startswith("javascript:"):
            raise ValueError("javascript: URIs are forbidden")
        if lowered.startswith("data:"):
            raise ValueError("data: URIs are forbidden")
        if value.startswith("//"):
            raise ValueError("protocol-relative URLs are forbidden")
        if "://" in value:
            raise ValueError("absolute URLs are forbidden; use relative paths")
        if not value.startswith("/"):
            raise ValueError("navigate path must start with '/'")
        return value

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "NavigateAction":
        if bool(self.path) == bool(self.url_ref):
            raise ValueError("navigate requires exactly one of 'path' or 'url_ref'")
        return self


class InspectAssetAction(_ActionModel):
    asset_ref: str


class StoreNoteAction(_ActionModel):
    note_type: str
    content: dict[str, Any]

    @field_validator("note_type")
    @classmethod
    def _validate_note_type(cls, value: str) -> str:
        if value not in VALID_NOTE_TYPES:
            raise ValueError(f"Invalid note_type: {value!r}")
        return value


class SubmitCandidateAction(_ActionModel):
    category: str
    description: str
    evidence_refs: list[str]

    @field_validator("category", "description")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("candidate category and description are required")
        return value


class RequestPhaseTransitionAction(_ActionModel):
    from_phase: str
    to_phase: str
    reason: str
    evidence_refs: list[str]
    remaining_questions: list[str] | None = None


class StopAction(_ActionModel):
    reason: str


VALID_NOTE_TYPES = {"hypothesis", "gap", "credential_label", "route", "parameter", "candidate"}

_SCHEMA_MAP: dict[str, type[_ActionModel]] = {
    "observe_page": ObservePageAction,
    "navigate": NavigateAction,
    "inspect_asset": InspectAssetAction,
    "store_note": StoreNoteAction,
    "submit_candidate": SubmitCandidateAction,
    "request_phase_transition": RequestPhaseTransitionAction,
    "stop": StopAction,
}


class ActionEnvelope(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    action: str
    goal: str
    reason: str
    hypothesis: str
    parsed: Any


def parse_action(raw: dict[str, Any]) -> ActionEnvelope:
    if not isinstance(raw, dict):
        raise InvalidActionError("Action response must be a JSON object")
    action_name = raw.get("action")
    if not action_name or action_name not in _SCHEMA_MAP:
        raise InvalidActionError(f"Unknown action: {action_name!r}")

    goal = raw.get("goal", "")
    reason = raw.get("reason", "")
    hypothesis = raw.get("hypothesis", "")
    args = raw.get("args", {})
    if not isinstance(args, dict):
        raise InvalidActionError("'args' must be an object")

    try:
        parsed = _SCHEMA_MAP[action_name].model_validate(args)
    except ValidationError as exc:
        raise InvalidActionError(str(exc)) from exc

    return ActionEnvelope(
        action=action_name, goal=goal, reason=reason,
        hypothesis=hypothesis, parsed=parsed,
    )
```
