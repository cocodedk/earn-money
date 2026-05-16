"""Strict typed LLM action schema for the probe loop.

The LLM returns exactly one of these JSON objects per turn.
Paths are always relative — the base URL is never exposed to the model.
"""
from __future__ import annotations

import json
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


def parse_action(
    raw: str,
) -> GetAction | PostAction | SetHeaderAction | StoreAction | ReportCandidateAction | StopAction:
    """Parse and validate a JSON string from the LLM into a typed action."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ActionParseError(f"Invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ActionParseError("Action must be a JSON object")

    tool = data.get("tool")
    if not isinstance(tool, str) or tool not in _TOOL_MAP:
        raise ActionParseError(f"Unknown tool: {tool!r}")

    cls = _TOOL_MAP[tool]
    try:
        return cls.model_validate(data)  # type: ignore[return-value]
    except Exception as e:
        raise ActionParseError(str(e)) from e
