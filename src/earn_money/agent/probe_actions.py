"""Strict typed LLM action schema for the probe loop.

The LLM returns exactly one of these JSON objects per turn.
Paths are always relative — the base URL is never exposed to the model.
"""
from __future__ import annotations

import json
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── individual action types ───────────────────────────────────────────────────


class GetArgs(_StrictBase):
    path: str
    params: dict[str, str] | None = None


class PostArgs(_StrictBase):
    path: str
    json_body: dict[str, Any] | None = Field(None, alias="json")
    data: dict[str, str] | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SetHeaderArgs(_StrictBase):
    name: str
    value: str


class StoreArgs(_StrictBase):
    kind: Literal["token", "id"]
    key: str
    value: str


class ReportCandidateArgs(_StrictBase):
    signal_type: str
    target: str
    evidence: str
    confidence: Literal["low", "medium", "high"]


class StopArgs(_StrictBase):
    reason: str = "done"


# ── union action model ────────────────────────────────────────────────────────


class GetAction(_StrictBase):
    tool: Literal["get"]
    category: Literal["http_get"]
    args: GetArgs


class PostAction(_StrictBase):
    tool: Literal["post"]
    category: Literal["http_post"]
    args: PostArgs


class SetHeaderAction(_StrictBase):
    tool: Literal["set_header"]
    category: Literal["auth"]
    args: SetHeaderArgs


class StoreAction(_StrictBase):
    tool: Literal["store"]
    category: Literal["store_memory"]
    args: StoreArgs


class ReportCandidateAction(_StrictBase):
    tool: Literal["report_candidate"]
    category: Literal["report_candidate"]
    args: ReportCandidateArgs


class StopAction(_StrictBase):
    tool: Literal["stop"]
    category: Literal["stop"]
    args: StopArgs = Field(default_factory=StopArgs)


ProbeAction = Annotated[
    GetAction | PostAction | SetHeaderAction | StoreAction | ReportCandidateAction | StopAction,
    Field(discriminator="tool"),
]


class ActionEnvelope(_StrictBase):
    """Top-level wrapper — parse the raw LLM JSON through this."""

    tool: str
    category: str
    args: dict[str, Any] = Field(default_factory=dict)


class ActionParseError(Exception):
    pass


_TOOL_MAP: dict[str, type[_StrictBase]] = {
    "get": GetAction,
    "post": PostAction,
    "set_header": SetHeaderAction,
    "store": StoreAction,
    "report_candidate": ReportCandidateAction,
    "stop": StopAction,
}

_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(?P<body>.*?)\n?\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _try_load(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


_ParsedAction = (
    GetAction | PostAction | SetHeaderAction
    | StoreAction | ReportCandidateAction | StopAction
)


def parse_action_with_recovery(raw: str) -> tuple[_ParsedAction, bool]:
    """Parse `raw` into a typed action. Returns `(action, parse_recovered)`
    where `parse_recovered` is True when the happy-path `json.loads` failed
    and one of the recovery layers had to fire."""
    data = _try_load(raw)
    recovered = False
    if data is None:
        recovered = True
        m = _FENCE_RE.match(raw)
        if m:
            data = _try_load(m.group("body"))
        if data is None:
            i, j = raw.find("{"), raw.rfind("}")
            if 0 <= i < j:
                data = _try_load(raw[i : j + 1])
        if data is None:
            raise ActionParseError(f"Invalid JSON: could not parse {raw[:80]!r}")

    tool = data.get("tool")
    if not isinstance(tool, str) or tool not in _TOOL_MAP:
        raise ActionParseError(f"Unknown tool: {tool!r}")
    cls = _TOOL_MAP[tool]
    try:
        action = cls.model_validate(data)
    except Exception as e:
        raise ActionParseError(str(e)) from e
    return action, recovered  # type: ignore[return-value]  # cls.model_validate returns _StrictBase, not the concrete subclass


def parse_action(raw: str) -> _ParsedAction:
    """Existing API — preserved unchanged. Drops the recovery flag."""
    action, _ = parse_action_with_recovery(raw)
    return action
