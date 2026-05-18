"""Map a task type to a model ID per spec §3 + §4.

Five profiles, each backed by its own env var, plus a global default.
The router itself is stateless — it just reads `os.environ` and falls
back deterministically.

Fallback chain for `resolve_model(task)`:
    1. The profile-specific env var (e.g. `OPENROUTER_MODEL_CODING_SECURITY`).
    2. `OPENROUTER_DEFAULT_MODEL`.
    3. `RouterUnconfigured` raised — operator must set at least one.
"""

from __future__ import annotations

import os
from enum import StrEnum


class TaskType(StrEnum):
    """Spec §4 task taxonomy. New values must be added to `_PROFILE_ENV`."""

    DEFAULT_ASSISTANT = "default_assistant"
    CODING_SECURITY = "coding_security"
    REPORT_WRITING = "report_writing"
    STRUCTURED_EXTRACTION = "structured_extraction"
    DEEP_REASONING = "deep_reasoning"
    AGENT_PLANNING = "agent_planning"


_PROFILE_ENV: dict[TaskType, str] = {
    TaskType.DEFAULT_ASSISTANT:     "OPENROUTER_MODEL_DEFAULT_ASSISTANT",
    TaskType.CODING_SECURITY:       "OPENROUTER_MODEL_CODING_SECURITY",
    TaskType.REPORT_WRITING:        "OPENROUTER_MODEL_REPORT_WRITING",
    TaskType.STRUCTURED_EXTRACTION: "OPENROUTER_MODEL_STRUCTURED_EXTRACTION",
    TaskType.DEEP_REASONING:        "OPENROUTER_MODEL_DEEP_REASONING",
    TaskType.AGENT_PLANNING:        "OPENROUTER_MODEL_AGENT_PLANNING",
}

_GLOBAL_DEFAULT_ENV = "OPENROUTER_DEFAULT_MODEL"


class RouterUnconfigured(Exception):
    """No model could be resolved — operator must set at least one env var."""


def coerce_task(value: str | TaskType | None) -> TaskType:
    """Normalise a string or None into a `TaskType`.

    Unknown strings collapse to `DEFAULT_ASSISTANT` (spec §4: 'unknown
    task types should either raise or fall back to default_assistant
    depending on the existing project style' — we fall back).
    None also collapses to `DEFAULT_ASSISTANT`.
    """
    if value is None:
        return TaskType.DEFAULT_ASSISTANT
    if isinstance(value, TaskType):
        return value
    try:
        return TaskType(value)
    except ValueError:
        return TaskType.DEFAULT_ASSISTANT


def resolve_model(task: str | TaskType | None) -> str:
    """Return the configured model ID for `task` (or default).

    Spec §4 fallback rules: profile env → global default env → error.
    """
    chosen = coerce_task(task)
    specific = os.environ.get(_PROFILE_ENV[chosen])
    if specific:
        return specific
    fallback = os.environ.get(_GLOBAL_DEFAULT_ENV)
    if fallback:
        return fallback
    raise RouterUnconfigured(
        f"no model configured for task {chosen.value!r}; "
        f"set {_PROFILE_ENV[chosen]} or {_GLOBAL_DEFAULT_ENV}"
    )


def profile_env_var(task: TaskType) -> str:
    """Return the env-var name that configures the model for `task`."""
    return _PROFILE_ENV[task]


def all_profile_envs() -> tuple[str, ...]:
    """Lookup helper for docs/diagnostics."""
    return (*_PROFILE_ENV.values(), _GLOBAL_DEFAULT_ENV)
