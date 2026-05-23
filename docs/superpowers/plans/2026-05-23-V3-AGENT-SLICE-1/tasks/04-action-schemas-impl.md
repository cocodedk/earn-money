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

