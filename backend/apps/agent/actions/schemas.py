from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

_BLOCKED_URL_PREFIXES = ("javascript:", "data:", "//")
_BLOCKED_URL_PATTERNS = ("://",)

_VALID_NOTE_TYPES = frozenset(
    {"hypothesis", "gap", "credential_label", "route", "parameter", "candidate", "form"}
)


class InvalidActionError(ValueError):
    """Raised when an action is unknown or has invalid fields."""


def _validate_url(value: str | None, field_name: str) -> None:
    if value is None:
        return
    for prefix in _BLOCKED_URL_PREFIXES:
        if value.startswith(prefix):
            raise InvalidActionError(
                f"{field_name} must not start with {prefix!r}: {value!r}"
            )
    for pattern in _BLOCKED_URL_PATTERNS:
        if pattern in value:
            raise InvalidActionError(
                f"{field_name} must not contain {pattern!r}: {value!r}"
            )


@dataclass
class ObservePageAction:
    include_screenshot: bool = False
    element_ids: list[str] | None = None


@dataclass
class NavigateAction:
    path: str | None = None
    url_ref: str | None = None

    def __post_init__(self) -> None:
        _validate_url(self.path, "path")
        _validate_url(self.url_ref, "url_ref")


@dataclass
class InspectAssetAction:
    asset_ref: str


@dataclass
class StoreNoteAction:
    note_type: str
    content: dict

    def __post_init__(self) -> None:
        if self.note_type not in _VALID_NOTE_TYPES:
            raise InvalidActionError(
                f"Invalid note_type {self.note_type!r}. "
                f"Valid types: {sorted(_VALID_NOTE_TYPES)}"
            )


@dataclass
class SubmitCandidateAction:
    category: str
    description: str
    evidence_refs: list[str]

    def __post_init__(self) -> None:
        if not self.category:
            raise InvalidActionError("submit_candidate requires a non-empty category")
        if not self.description:
            raise InvalidActionError("submit_candidate requires a non-empty description")
        if not isinstance(self.evidence_refs, list):
            raise InvalidActionError("submit_candidate evidence_refs must be a list")


@dataclass
class RequestPhaseTransitionAction:
    from_phase: str
    to_phase: str
    reason: str
    evidence_refs: list[str]
    remaining_questions: list[str] | None = None


@dataclass
class StopAction:
    reason: str


@dataclass
class ClickAction:
    element_id: str

    def __post_init__(self) -> None:
        if not self.element_id:
            raise InvalidActionError("click requires a non-empty element_id")


_SAFE_HTTP_METHODS = frozenset({"GET", "HEAD"})


@dataclass
class HttpRequestAction:
    method: str
    path: str

    def __post_init__(self) -> None:
        if self.method not in _SAFE_HTTP_METHODS:
            raise InvalidActionError(
                f"http_request method must be GET or HEAD, got {self.method!r}"
            )
        if not self.path:
            raise InvalidActionError("http_request requires a non-empty path")
        _validate_url(self.path, "path")


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


@dataclass
class ActionEnvelope:
    action: str
    goal: str
    reason: str
    hypothesis: str
    parsed: Any


_ACTION_MAP: dict[str, type] = {
    "observe_page": ObservePageAction,
    "navigate": NavigateAction,
    "inspect_asset": InspectAssetAction,
    "store_note": StoreNoteAction,
    "submit_candidate": SubmitCandidateAction,
    "request_phase_transition": RequestPhaseTransitionAction,
    "stop": StopAction,
    "click": ClickAction,
    "http_request": HttpRequestAction,
    "fill_form": FillFormAction,
    "submit_form": SubmitFormAction,
}

_REQUIRED_ENVELOPE_KEYS = {"action", "goal", "reason", "hypothesis"}


def _build_action(name: str, raw: dict) -> Any:
    cls = _ACTION_MAP.get(name)
    if cls is None:
        raise InvalidActionError(f"Unknown action {name!r}")
    # Extract only keys that are declared fields on the target dataclass.
    # This avoids envelope key collisions (e.g. both envelope and StopAction have "reason").
    field_names = {f.name for f in dataclasses.fields(cls)}
    payload = {k: v for k, v in raw.items() if k in field_names}
    try:
        return cls(**payload)
    except TypeError as exc:
        raise InvalidActionError(f"Invalid fields for {name!r}: {exc}") from exc


def parse_action(raw: dict) -> ActionEnvelope:
    """Parse and validate a raw action dict into a typed ActionEnvelope."""
    for key in _REQUIRED_ENVELOPE_KEYS:
        if key not in raw:
            raise InvalidActionError(f"Missing required envelope field: {key!r}")
    name = raw["action"]
    parsed = _build_action(name, raw)
    return ActionEnvelope(
        action=name,
        goal=raw["goal"],
        reason=raw["reason"],
        hypothesis=raw["hypothesis"],
        parsed=parsed,
    )
